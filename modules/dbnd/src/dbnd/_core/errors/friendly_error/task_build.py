from __future__ import absolute_import

from dbnd._core.errors import DatabandBuildError, UnknownParameterError
from dbnd._core.errors.friendly_error.helpers import _band_call_str
from dbnd._core.utils.basics.text_banner import safe_string


def no_databand_context():
    return DatabandBuildError(
        "You are trying to create task without having active Databand context! "
        "You should have databand context while building/running tasks. "
        "You can create one inplace by adding `init_dbnd()` call"
    )


def unknown_parameter_in_constructor(constructor, param_name, task_parent):
    help_msg = "Remove {param_name} from constructor {constructor}".format(
        param_name=param_name, constructor=constructor
    )

    if task_parent:
        help_msg += " at %s method!" % _band_call_str(task_parent)

    return UnknownParameterError(
        "Unknown parameter '{param_name}' at {constructor}".format(
            constructor=constructor, param_name=param_name
        ),
        help_msg=help_msg,
    )


def pipeline_task_has_unassigned_outputs(task, param):
    return DatabandBuildError(
        "You have unassigned output '{param.name}' in task '{task}'".format(
            param=param, task=task
        ),
        help_msg="Check your {band} logic, Add self.{param.name} = SOME_TASK_OUTPUT".format(
            band=_band_call_str(task), param=param
        ),
    )


def failed_to_call_band(ex, task):
    return DatabandBuildError(
        "Failed to call '%s': %s" % (_band_call_str(task), ex),
        show_exc_info=False,
        nested_exceptions=[ex],
        help_msg="Check your %s logic" % _band_call_str(task),
    )


def failed_to_call(ex, task_cls):
    return DatabandBuildError(
        "Failed to invoke '%s': %s" % (_band_call_str(task_cls), ex),
        show_exc_info=False,
        nested_exceptions=[ex],
        help_msg="Check your %s logic" % _band_call_str(task_cls),
    )


def failed_to_assign_param_value_at_band(ex, param, value, task):
    return DatabandBuildError(
        "Failed to assign '{value}' to parameter {param.name} at '{band}': {ex}".format(
            band=_band_call_str(task), value=value, ex=ex, param=param
        ),
        show_exc_info=False,
        nested_exceptions=[ex],
        help_msg="Check your %s logic" % _band_call_str(task),
    )


def iteration_over_task(task):
    help_msg = "You can iterate over task results, but not the task itself"
    if hasattr(task, "result"):
        help_msg = (
            "If you want to access task results, use {task}().result notation."
            " Probably this task has outputs defined via return value as well as regular parameter".format(
                task=task.get_task_family()
            )
        )
    # we have to return type error,
    # as sometimes we traverse task..and we need indication that it can't be  traversed
    # we can't use BuildError here
    return TypeError(
        "Task '{task}' can not be unpacked or iterated. {help_msg}".format(
            task=task.get_task_family(), help_msg=help_msg
        )
    )


def failed_to_import_pyspark(task, ex):
    return DatabandBuildError(
        "Tried to create spark session for a task {task} but failed to import pyspark".format(
            task=task.get_task_family
        ),
        show_exc_info=False,
        nested_exceptions=[ex],
        help_msg="Check your environment for pyspark installation.",
    )
