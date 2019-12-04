# -*- coding: utf-8 -*-
#
# Copyright 2015 Spotify AB
# Modifications copyright (C) 2018 databand.ai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
The abstract :py:class:`Task` class.
It is a central concept of databand and represents the state of the workflow.
See :doc:`/tasks` for an overview.
"""
import logging
import typing

from typing import Dict, Optional

import six

from dbnd._core.constants import TaskType
from dbnd._core.decorator.task_decorator_spec import _TaskDecoratorSpec
from dbnd._core.errors import friendly_error
from dbnd._core.parameter.parameter_definition import ParameterDefinition
from dbnd._core.task_build.task_definition import TaskDefinition
from dbnd._core.task_build.task_metaclass import TaskMetaclass
from dbnd._core.task_ctrl.task_auto_values import TaskAutoParamsReadWrite
from dbnd._core.task_ctrl.task_meta import TaskMeta
from dbnd._core.task_ctrl.task_parameters import TaskParameters
from dbnd._core.utils.basics.nothing import NOTHING


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from dbnd._core.settings import DatabandSettings


@six.add_metaclass(TaskMetaclass)
class _BaseTask(object):
    # override to change get_task_family() -> changes task_family
    _conf__task_family = None
    task_namespace = NOTHING

    _conf__task_type_name = TaskType.python
    _conf__task_ui_color = None
    #####
    # override output path format
    _conf__base_output_path_fmt = None

    # stores call spec for the @task definition
    _conf__decorator_spec = None  # type: Optional[_TaskDecoratorSpec]

    _conf__tracked = True
    _conf__no_child_params = False

    _conf__require_run_dump_file = False

    # this one enables the autoread.
    _conf_auto_read_params = True
    # this is the state of autoread
    _task_auto_read_original = None
    _task_auto_read = None
    ####
    # execution
    # will be used by Registry
    task_definition = None  # type: TaskDefinition

    # user can override this with his configuration
    defaults = None  # type: Dict[ParameterDefinition, any()]

    @classmethod
    def get_task_family(cls):
        return cls.task_definition.task_family

    def __init__(self, **kwargs):
        super(_BaseTask, self).__init__()

        # most of the time we will use it as TaskMetaCtrl - we want this to be type hint!
        self.task_meta = kwargs["task_meta"]  # type: TaskMeta
        self._params = TaskParameters(self)

        for p_value in self.task_meta.task_params:
            setattr(self, p_value.name, p_value.value)

        self._task_auto_read_current = None
        self._task_auto_read_origin = None

    @property
    def task_id(self):
        return self.task_meta.task_id

    @property
    def task_signature(self):
        return self.task_meta.task_signature

    @property
    def task_name(self):
        return self.task_meta.task_name

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__
            and self._params.get_param_values() == other._params.get_param_values()
        )

    def __hash__(self):
        return hash(self.task_id)

    def __repr__(self):
        """
        Build a task representation like `MyTask(param1=1.5, param2='5')`
        """
        return "%s" % self.task_meta.task_id

    def __str__(self):
        """
        Build a task representation like `MyTask(param1=1.5, param2='5')`
        """
        return self.task_meta.task_id

    @property
    def friendly_task_name(self):
        if self.task_name != self.task_meta.task_family:
            return "%s[%s]" % (self.task_name, self.task_meta.task_family)
        return self.task_name

    def __getattribute__(self, name):
        def _get(n):
            return super(_BaseTask, self).__getattribute__(n)

        value = _get(name)
        try:
            _task_auto_read = _get("_task_auto_read")
        except Exception:
            return value

        # already cached
        if _task_auto_read is None or name in _task_auto_read:
            return value

        parameter = _get("_params").get_param(name)

        # we are not parameter
        # or there is nothing to "deferefence"
        # TODO: rebase  : value is None
        if not parameter:
            return value

        runtime_value = parameter.calc_runtime_value(value, task=self)

        if parameter.is_output():
            # if it's outpus, we should not "cache" it
            # otherwise we will try to save it on autosave ( as it was changed)
            return runtime_value
        # for the cache, so next time we don't need to calculate it
        setattr(self, name, runtime_value)
        _task_auto_read.add(name)
        return runtime_value

    def _auto_load_save_params(
        self, auto_read=False, save_on_change=False, normalize_on_change=False
    ):
        c = TaskAutoParamsReadWrite(
            task=self,
            auto_read=auto_read,
            save_on_change=save_on_change,
            normalize_on_change=normalize_on_change,
        )
        return c.auto_load_save_params()

    def clone(self, cls=None, **kwargs):
        """
        Creates a new instance from an existing instance where some of the args have changed.

        There's at least two scenarios where this is useful (see test/clone_test.py):

        * remove a lot of boiler plate when you have recursive dependencies and lots of args
        * there's task inheritance and some logic is on the base class

        :param cls:
        :param kwargs:
        :return:
        """
        if cls is None:
            cls = self.__class__

        new_k = {}
        for param_name, param_class in six.iteritems(cls.task_definition.task_params):
            if param_name in kwargs:
                new_k[param_name] = kwargs[param_name]
            elif hasattr(self, param_name):
                new_k[param_name] = getattr(self, param_name)

        return cls(**new_k)

    @property
    def settings(self):
        # type: () -> DatabandSettings

        return self.task_meta.dbnd_context.settings

    def __iter__(self):
        raise friendly_error.task_build.iteration_over_task(self)

    def _initialize(self):
        pass

    def _task_banner(self, banner, verbosity):
        """
        customize task banner
        """
        return

    def _validate(self):
        """
        will be called after after object is created
        :return:
        """
        return
