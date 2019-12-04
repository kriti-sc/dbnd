import logging
import typing

from dbnd._core.constants import TaskRunState
from dbnd._core.task_run.task_run_logging import TaskRunLogManager
from dbnd._core.task_run.task_run_meta_files import TaskRunMetaFiles
from dbnd._core.task_run.task_run_runner import TaskRunRunner
from dbnd._core.task_run.task_run_tracker import TaskRunTracker
from dbnd._core.tracking.tracking_store_console import ConsoleStore
from dbnd._core.utils.string_utils import clean_job_name, clean_job_name_dns1123
from dbnd._core.utils.uid_utils import get_uuid
from targets import target


logger = logging.getLogger(__name__)
if typing.TYPE_CHECKING:
    from dbnd._core.run.databand_run import DatabandRun
    from dbnd._core.task.task import Task
    from dbnd._core.settings import EngineConfig


class TaskRun(object):
    def __init__(
        self,
        task,
        run,
        task_af_id=None,
        try_number=1,
        _uuid=None,
        is_dynamic=None,
        task_engine=None,
    ):
        # type: (Task, DatabandRun, str, int, str, bool, EngineConfig)-> None
        # actually this is used as Task uid
        self.task_run_uid = _uuid or get_uuid()
        # we can handle only single attempt per run for now
        # this is the "task_run_attempt_uid" in db
        self.task_run_attempt_uid = get_uuid()
        self.task = task  # type: Task
        self.run = run  # type: DatabandRun
        self.task_engine = task_engine
        self.try_number = try_number
        self.is_dynamic = is_dynamic if is_dynamic is not None else task.task_is_dynamic
        self.is_system = task.task_is_system

        self.task_af_id = task_af_id or self.task.task_id

        # used by all kind of submission controllers
        # TODO: should job_name be based on task_af_id or task_id ?
        self.job_name = clean_job_name(self.task_af_id).lower()
        self.job_id = self.job_name + "_" + str(self.task_run_uid)[:8]

        # DNS-1123 subdomain name (k8s)
        self.job_id__dns1123 = clean_job_name_dns1123(
            "dbnd.{task_family}.{task_name}".format(
                task_family=self.task.task_meta.task_family,
                task_name=self.task.task_meta.task_name,
            ),
            postfix=".%s" % str(self.task_run_uid)[:8],
        )

        self.attempt_folder = task._meta_output.folder(
            "attempt_%s" % self.task_run_attempt_uid, extension=None
        )
        self.meta_files = TaskRunMetaFiles(self.attempt_folder)
        # custom per task engine , or just use one from global env
        dbnd_local_root = (
            self.task_engine.dbnd_local_root or self.run.env.dbnd_local_root
        )
        self.local_task_run_root = (
            dbnd_local_root.folder(run.run_folder_prefix)
            .folder("tasks")
            .folder(self.task.task_id)
        )

        # TODO: inherit from parent task if disabled
        self.is_tracked = task._conf__tracked

        if self.is_tracked and self.run.is_tracked:
            tracking_store = self.run.context.tracking_store
        else:
            tracking_store = ConsoleStore()

        self.tracking_store = tracking_store
        self.tracker = TaskRunTracker(task_run=self, tracking_store=tracking_store)

        self.runner = TaskRunRunner(task_run=self)
        self.log = TaskRunLogManager(task_run=self)
        self.task_tracker_url = self.tracker.task_run_url()
        self.external_resource_urls = dict()
        self.errors = []

        self.is_root = False
        self.is_reused = False
        self.is_skipped = False

        # Task can be skipped as it's not required by any other task scheduled to run
        self.is_skipped_as_not_required = False

        self.airflow_context = None
        self._task_run_state = None

        self.start_time = None
        self.finished_time = None

    @property
    def task_run_env(self):
        return self.run.context.task_run_env

    def task_run_attempt_file(self, *path):
        return target(self.attempt_folder, *path)

    @property
    def last_error(self):
        return self.errors[-1] if self.errors else None

    def _get_log_files(self):

        log_local = None
        if self.log.local_log_file:
            log_local = self.log.local_log_file.path

        log_remote = None
        if self.log.remote_log_file:
            log_remote = self.log.remote_log_file.path

        return log_local, log_remote

    @property
    def task_run_state(self):
        return self._task_run_state

    @task_run_state.setter
    def task_run_state(self, value):
        raise AttributeError("Please use explicit .set_task_run_state()")

    def set_task_run_state(self, state, track=True, error=None):
        # type: (TaskRunState, bool, Any) -> bool
        # Optional bool track param - will send tracker.set_task_run_state() by default
        if not state or self._task_run_state == state:
            return False

        if error:
            self.errors.append(error)

        self._task_run_state = state
        if track:
            self.tracking_store.set_task_run_state(
                task_run=self, state=state, error=error
            )
        return True

    def set_task_reused(self):
        self._task_run_state = TaskRunState.SUCCESS
        self.tracking_store.set_task_reused(task_run=self)

    def set_external_resource_urls(self, logs_dict):
        # if value is None skip
        if logs_dict is None:
            # TODO: Throw exception?
            return

        for link in logs_dict:
            if not logs_dict[link]:
                # Dict has empty fields
                # TODO: Throw exception?
                return

        self.external_resource_urls.update(logs_dict)
        self.tracking_store.save_external_links(
            task_run=self, external_links_dict=logs_dict
        )

    def __repr__(self):
        return "TaskRun(%s, %s)" % self.task.task_name, self.task_run_state
