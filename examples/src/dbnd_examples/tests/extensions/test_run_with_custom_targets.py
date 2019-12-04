import logging

from dbnd.testing import assert_run_task
from dbnd_examples.extensions.custom_target import CustomIOPipeline


logger = logging.getLogger(__name__)


class TestRunWithCustomTargets(object):
    def test_parameter_with_multiple_partitions(self):
        assert_run_task(CustomIOPipeline())
