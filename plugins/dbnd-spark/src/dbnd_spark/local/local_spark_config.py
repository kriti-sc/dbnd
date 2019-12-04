from dbnd import parameter
from dbnd._core.task.config import Config


class SparkLocalConfig(Config):
    """Apache Spark local deployment"""

    # we don't want spark class to inherit from this one, as it should has Config behaviour
    _conf__task_family = "spark_local"

    conn_id = parameter.value(
        default="spark_local",
        description="local spark connection settings (SPARK_HOME)",
    )

    def get_spark_ctrl(self, task_run):
        from dbnd_spark.local.local_spark import LocalSparkExecutionCtrl

        return LocalSparkExecutionCtrl(self, job=task_run)
