import logging

from dbnd import parameter
from dbnd._core.errors import DatabandRuntimeError
from dbnd._core.task.task import Task
from dbnd._core.utils.better_subprocess import run_cmd
from dbnd._core.utils.project.project_fs import project_path


logger = logging.getLogger(__name__)


class DockerBuild(Task):
    use_koniko = parameter(default=True)[bool]

    docker_file = parameter(default=project_path("Dockerfile"))[str]
    image_name = parameter()[str]
    tag = parameter(default="latest")[str]
    label = parameter(default="")[str]
    push = parameter(default=True)[bool]
    target = parameter(default=None)[str]

    working_dir = parameter(default=None)[str]

    kaniko_command = parameter(default=None)[str]
    context = parameter(default=None)[str]
    destinations = parameter(default=None)[list]
    build_args = parameter(default=None)[list]

    full_image_name = None
    computed_tag = None
    image_name_with_tag = None

    def run(self):
        if self.use_koniko:
            return self.run_using_kaniko()
        else:
            return self.run_using_docker_build()

    def run_using_docker_build(self):
        if self.tag:
            self.image_name_with_tag = "{}:{}".format(self.image_name, self.tag)
        else:
            self.image_name_with_tag = self.full_image_name

        try:
            cmd = "docker build -t {} -f {} .".format(
                self.image_name_with_tag, self.docker_file
            )
            if self.label:
                cmd = cmd + " --label " + self.label
            if self.target:
                cmd = cmd + " --target " + self.target
            logger.info("Running docker build: %s", cmd)
            cwd = self.working_dir or project_path()
            run_cmd(cmd, shell=True, cwd=cwd)

        except Exception as e:
            raise DatabandRuntimeError(
                "failed building docker image {}".format(self.image_name_with_tag),
                nested_exceptions=[e],
            )

        if self.push:
            try:
                cmd = "docker push {}".format(self.image_name_with_tag)
                logger.info("Running docker push: '%s'", cmd)
                run_cmd(cmd, shell=True)

            except Exception as e:
                raise DatabandRuntimeError(
                    "failed to push docker image {}".format(self.image_name_with_tag),
                    nested_exceptions=[e],
                )
        else:
            logger.info("skipping docker push")

        return self.image_name_with_tag

    def run_using_kaniko(self):
        if self.tag:
            self.image_name_with_tag = "{}:{}".format(self.image_name, self.tag)
        else:
            self.image_name_with_tag = self.full_image_name

        command = "{} -c {} -d {} --cache=true".format(self.kaniko_command, self.context, self.docker_file)

        if self.destinations is None or len(self.destinations) == 0:
            command = command + "--no-push"
        else:
            destination_list = ["--destination {}".format(destination) for destination in self.destinations]
            command = command + "".join(destination_list)

        if self.build_args is not None and len(self.build_args):
            build_args_list = ["--build-args {}".format(arg) for arg in self.build_args]
            command = command + "".join(build_args_list)

        if self.label:
            command = command + " --label " + self.label

        if self.target:
            command = command + " --target " + self.target

        try:
            run_cmd(command, shell=True, cwd=project_path())
        except Exception as e:
            raise DatabandRuntimeError(
                "failed building docker image {}".format("?"),
                nested_exceptions=[e],
            )

        return self.image_name_with_tag
