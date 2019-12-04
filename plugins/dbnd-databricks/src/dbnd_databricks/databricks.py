import logging
import time

from dbnd._core.current import current_task_run
from dbnd._core.errors import DatabandError
from dbnd._core.task_run.task_engine_ctrl import TaskEnginePolicyCtrl
from dbnd._core.utils.basics.text_banner import TextBanner
from dbnd._core.utils.structures import list_of_strings
from dbnd_aws.aws_sync_ctrl import AwsSyncCtrl
from dbnd_spark.spark import SparkCtrl, SparkTask


logger = logging.getLogger(__name__)


# to do - add on kill handling (this is not urgent, as anyway it will shutdown the machines at the end of execution)
class DatabricksCtrl(TaskEnginePolicyCtrl, AwsSyncCtrl, SparkCtrl):
    def __init__(self, task_run):
        super(DatabricksCtrl, self).__init__(task=task_run.task, job=task_run)
        self.databricks_config = task_run.task.spark_engine

    def _handle_databricks_operator_execution(self, run_id, hook, task_id):
        """
        Handles the Airflow + Databricks lifecycle logic for a Databricks operator
        :param run_id: Databricks run_id
        :param hook: Airflow databricks hook
        :param task_id: Databand Task Id.

        """
        b = TextBanner(
            "Spark task %s is submitted to Databricks cluster:" % task_id, color="cyan"
        )
        url = hook.get_run_page_url(run_id)
        self.task_run.set_external_resource_urls({"databricks url": url})
        b.column("databricks URL", url)
        logger.info("/n" + b.get_banner_str())
        while True:
            b.column("databricks URL", url)
            run_state = hook.get_run_state(run_id)
            if run_state.is_terminal:
                if run_state.is_successful:
                    b.column("Task completed successfully", task_id)
                    b.column("State:", run_state.life_cycle_state)
                    b.column("Message:", run_state.state_message)
                    break
                else:
                    error_message = "{t} failed with terminal state: {s}, please try visit databricks site {w} for more info".format(
                        t=task_id, s=run_state, w=url
                    )
                    raise DatabandError(error_message)
            else:
                b.column("State:", run_state.life_cycle_state)
                b.column("Message:", run_state.state_message)
                time.sleep(self.databricks_config.status_polling_interval_seconds)
            logger.info("/n" + b.get_banner_str())

    def _run_spark_submit(self, spark_submit_parameters):
        task = self.task  # type: SparkTask

        _config = task.spark_engine
        new_cluster = {
            "num_workers": self.databricks_config.num_workers,
            "spark_version": self.databricks_config.spark_version,
            "spark_conf": self.databricks_config.spark_conf,
            "node_type_id": self.databricks_config.node_type_id,
            "init_scripts": self.databricks_config.init_script,
            "spark_env_vars": self.databricks_config.spark_env_vars,
        }
        if self.task_env.cloud_type == "aws":
            new_cluster["aws_attributes"] = {
                "instance_profile_arn": self.databricks_config.aws_instance_profile_arn,
                "ebs_volume_type": self.databricks_config.aws_ebs_volume_type,
                "ebs_volume_count": self.databricks_config.aws_ebs_volume_count,
                "ebs_volume_size": self.databricks_config.aws_ebs_volume_size,
            }
        else:
            # need to see if there are any relevant setting for azure or other databricks envs.
            pass

        # since airflow connector for now() does not support spark_submit_task, it is implemented this way.
        databricks_json = {
            "spark_submit_task": {"parameters": spark_submit_parameters},
            "new_cluster": new_cluster,
            "run_name": task.task_id,
        }

        from airflow.contrib.hooks.databricks_hook import DatabricksHook

        hook = DatabricksHook(_config.conn_id, retry_limit=3, retry_delay=1)
        run_id = hook.submit_run(databricks_json)
        hook.log.setLevel(logging.WARNING)
        self._handle_databricks_operator_execution(run_id, hook, _config.task_id)
        hook.log.setLevel(logging.INFO)

    def run_pyspark(self, pyspark_script):
        # should be reimplemented using SparkSubmitHook (maybe from airflow)
        # note that config jars are not supported.
        spark_submit_parameters = [self.sync(pyspark_script)] + (
            list_of_strings(self.task.application_args())
        )
        return self._run_spark_submit(spark_submit_parameters)

    def run_spark(self, main_class):
        jars_list = []
        jars = self.config.jars
        if jars:
            jars_list = ["--jars"] + jars
        # should be reimplemented using SparkSubmitHook (maybe from airflow)
        spark_submit_parameters = [
            "--class",
            main_class,
            self.sync(self.config.main_jar),
        ] + (list_of_strings(self.task.application_args()) + jars_list)
        return self._run_spark_submit(spark_submit_parameters)

    def _report_step_status(self, step):
        logger.info(self._get_step_banner(step))

    def _get_step_banner(self, step):
        """
        {
          'id': 6,
          'state': 'success',
        }
        """
        t = self.task
        b = TextBanner("Spark Task %s is running at Emr:" % t.task_id, color="yellow")

        b.column("TASK", t.task_id)
        b.column("EMR STEP STATE", step["Step"]["Status"]["State"])

        tracker_url = current_task_run().task_tracker_url
        if tracker_url:
            b.column("DATABAND LOG", tracker_url)

        b.new_line()
        b.column("EMR STEP ID", step["Step"]["Id"])
        b.new_section()
        return b.getvalue()
