import logging
import typing

from typing import List

from dbnd._core.run.run_ctrl import RunCtrl


if typing.TYPE_CHECKING:
    from dbnd._core.tracking.tracking_store import TrackingStore
    from dbnd._core.task_run.task_run import TaskRun

logger = logging.getLogger(__name__)


class RunTracker(RunCtrl):
    def __init__(self, run, tracking_store):
        super(RunTracker, self).__init__(run)
        self.tracker_url = self.settings.core.tracker_url
        self.tracking_store = tracking_store  # type: TrackingStore

        if self.tracker_url:
            self.run_url = "{tracker_url}/app/jobs/{job_name}/{run_uid}".format(
                tracker_url=self.tracker_url,
                job_name=self.run.job_name,
                run_uid=self.run.run_uid,
            )
        else:
            self.run_url = None

    # Following handlers only works for Databand RUN, not for the specific task!
    def init_run(self):
        """
        runs for the whole dag
        we call it only for the root dag
        """
        if not self.run.is_tracked:
            return
        self.tracking_store.init_run(run=self.run)
        logger.info("Run tracking info has been committed.")

    def set_run_state(self, state):
        if not self.run.is_tracked:
            return
        self.tracking_store.set_run_state(run=self.run, state=state)

    def add_task_runs(self, task_runs):
        if not self.run.is_tracked:
            return
        self.tracking_store.add_task_runs(run=self.run, task_runs=task_runs)

    def set_task_run_states(self, task_runs):
        # type: (List[TaskRun]) -> None
        if not self.run.is_tracked:
            return
        self.tracking_store.set_task_run_states(task_runs=task_runs)
