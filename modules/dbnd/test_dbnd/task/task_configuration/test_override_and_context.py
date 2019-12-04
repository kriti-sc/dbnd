import logging

from dbnd import PipelineTask, config, parameter, pipeline, run_task, task
from dbnd._core.configuration.pprint_config import pformat_current_config
from dbnd.tasks.basics.simplest import SimplestTask
from test_dbnd.factories import FooConfig, TTask
from test_dbnd.task_ctrl.test_task_log import WordCount, WordCountPipeline


logger = logging.getLogger()


@task
def task_from_config(parameter_from_config, expected):
    assert parameter_from_config == expected


class FirstTask(TTask):
    foo = parameter(default="FooConfig")[FooConfig]
    param = parameter(default="FirstTask.default")[str]


class SecondTask(FirstTask):
    param = "SecondTask.inline"

    defaults = {
        FooConfig.bar: "SecondTask.foo.defaults",
        FooConfig.quz: "SecondTask.foo.defaults",
    }


class ThirdTask(FirstTask):
    param = "ThirdTask.inline.param"
    defaults = {FooConfig.bar: "ThirdTask.defaults.foo.bar"}


class FirstPipeTask(PipelineTask):
    defaults = {FooConfig.bar: "FirstPipeTask.defaults.foo.bar"}

    def band(self):
        logger.info("FirstPipeTask.band : %s", pformat_current_config(config))
        self.third = ThirdTask(param="FirstPipeTask.third.ctor")


class SecondPipeTask(PipelineTask):
    defaults = {
        FooConfig.quz: "SecondPipeTask.defaults.foo.quz",
        ThirdTask.param: "SecondPipeTask.defaults.third.param",
    }

    def band(self):
        override = {
            FooConfig.quz: "SecondPipeTask.override.foo.quz"
        }  # overridden by self.config
        self.third = FirstPipeTask(override=override).third


class TestTaskOverrideAndContextConfig(object):
    def test_simple(self):
        t = FirstTask()

        assert "FirstTask.default" == t.param
        assert "from_config" == t.foo.bar
        assert "from_config" == t.foo.quz

    def test_inheritance(self):
        t = SecondTask()
        # defaults should override this values
        assert "SecondTask.foo.defaults" == t.foo.bar
        assert "SecondTask.foo.defaults" == t.foo.quz

        # checking inline override
        assert "SecondTask.inline" == t.param

    def test_inheritance_2(self):
        t = ThirdTask()

        assert "ThirdTask.inline.param" == t.param
        assert "ThirdTask.defaults.foo.bar" == t.foo.bar
        assert "from_config" == t.foo.quz

    def test_pipeline(self):
        t = FirstPipeTask()

        assert "FirstPipeTask.third.ctor" == t.third.param
        # foo bar should be from pipe because of defaults
        assert "FirstPipeTask.defaults.foo.bar" == t.third.foo.bar
        assert "from_config" == t.third.foo.quz

    def test_pipeline_2(self):
        t = SecondPipeTask()

        # pipeline defaults should not override task constructor
        third = t.third
        assert "FirstPipeTask.third.ctor" == third.param
        assert "FirstPipeTask.defaults.foo.bar" == third.foo.bar
        assert "SecondPipeTask.override.foo.quz" == third.foo.quz  # override section

    def test_override_simple(self):
        t = FirstTask(
            override={
                FirstTask.param: "override.param",
                FooConfig.bar: "override.foo.bar",
            }
        )

        assert "override.param" == t.param
        assert "override.foo.bar" == t.foo.bar
        assert "from_config" == t.foo.quz

    def test_override_inheritance_legacy(self):
        with config(
            {SecondTask.param: "config.context", FooConfig.bar: "config.context"}
        ):
            t = SecondTask()
            assert "config.context" == t.param
            assert "config.context" == t.foo.bar
            assert "SecondTask.foo.defaults" == t.foo.quz

    def test_override_inheritance_2(self):
        t = ThirdTask(
            override={
                ThirdTask.param: "override.third",
                FooConfig.bar: "override.third",
            }
        )

        assert "override.third" == t.param
        assert "override.third" == t.foo.bar
        assert "from_config" == t.foo.quz

    def test_override_inheritance_config(self):
        with config(
            {
                SecondTask.param: "from_config_context",
                FooConfig.bar: "from_config_context",
            }
        ):
            t = SecondTask()
            assert "from_config_context" == t.param, "t.param"
            assert "from_config_context" == t.foo.bar, "t.foo.bar"
            assert "SecondTask.foo.defaults" == t.foo.quz, "t.foo.quz"

    def test_override_pipeline(self):
        t = FirstPipeTask(
            override={ThirdTask.param: "override.param", FooConfig.bar: "override.bar"}
        )

        assert "override.param" == t.third.param
        assert "override.bar" == t.third.foo.bar
        assert "from_config" == t.third.foo.quz

    def test_override_pipeline_2(self):
        t = SecondPipeTask(override={FooConfig.quz: "override.quz"})

        assert "FirstPipeTask.third.ctor" == t.third.param
        assert "FirstPipeTask.defaults.foo.bar" == t.third.foo.bar

        # we override here and inside band
        # most recent one should be taken
        # otherwise the value would be 'override.quz'
        assert "SecondPipeTask.override.foo.quz" == t.third.foo.quz

    def test__regression__word_count_override(self):
        t = WordCountPipeline(override={WordCount.text: __file__})
        run_task(t)

        assert len(t.task_outputs["counter"].read()) > 50

    def test_override_str_key_config(self):
        @task
        def t_f(a=4):
            assert a == 5

        t_f.dbnd_run(override={"%s.t_f" % self.__module__: {"a": 5}})

    def test_per_task_name_config(self):
        @task
        def t_f(a=4):
            pass

        t1 = t_f.task(task_name="ttt", override={"ttt": {"a": 5}})
        assert t1.a == 5

        t2 = t_f.task(task_name="ttt", override={"ttt": {"a": 6}})
        assert t2.a == 6

    def test_internal_override(self):
        @pipeline
        def nested():
            return SimplestTask(simplest_param=1)

        @pipeline
        def t_search():
            result = []
            for i in range(5):
                nested_with_ovdrride = nested(override={SimplestTask.simplest_param: i})
                result.append(nested_with_ovdrride)
            return result

        actual = t_search.task()
        run = actual.dbnd_run()
        assert len(run.task_runs_by_id) == 12

    def test_override_config_values_simple(self):
        task_from_config.dbnd_run(expected="from_config")

    def test_override_config_values_from_context(self):
        with config(
            {"task_from_config": {"parameter_from_config": "from_context_override"}}
        ):
            assert (
                config.get("task_from_config", "parameter_from_config")
                == "from_context_override"
            )
            task_from_config.dbnd_run(expected="from_context_override")

    def test_override_config__override(self):
        task_from_config.dbnd_run(
            expected="from_override",
            override={task_from_config.task.parameter_from_config: "from_override"},
        )

    def test_override_config__context(self):
        # same problem as previous test
        with config(
            config_values={task_from_config.task.parameter_from_config: "from_context"}
        ):
            task_from_config.dbnd_run(expected="from_config")
