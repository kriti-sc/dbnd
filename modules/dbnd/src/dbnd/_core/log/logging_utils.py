import logging
import os
import sys

from contextlib import contextmanager

from dbnd._core.utils.platform import windows_compatible_mode
from targets.utils.path import safe_mkdirs


logger = logging.getLogger(__name__)


def _eset_handlers():
    root = logging.root
    map(root.removeHandler, root.handlers[:])
    map(root.removeFilter, root.filters[:])


def get_sentry_logging_config(sentry_url, sentry_env):
    import raven.breadcrumbs

    for ignore in (
        "sqlalchemy.orm.path_registry",
        "sqlalchemy.pool.NullPool",
        "raven.base.Client",
    ):
        raven.breadcrumbs.ignore_logger(ignore)

    return {
        "exception": {
            "level": "ERROR",
            "class": "raven.handlers.logging.SentryHandler",
            "dsn": sentry_url,
            "environment": sentry_env,
        }
    }


def symlink_latest_log(log_file, latest_log=None):
    if windows_compatible_mode:
        # there is no symlinks in windows
        return

    if latest_log is None:
        log_directory, log_filename = os.path.split(log_file)
        latest_log = os.path.join(log_directory, "latest")

    try:
        # if symlink exists but is stale, update it
        if os.path.islink(latest_log):
            if os.readlink(latest_log) != log_file:
                os.unlink(latest_log)
                os.symlink(log_file, latest_log)
        elif os.path.isdir(latest_log) or os.path.isfile(latest_log):
            logging.warning(
                "%s already exists as a dir/file. Skip creating symlink.", latest_log
            )
        else:
            os.symlink(log_file, latest_log)
    except OSError:
        logging.warning(
            "OSError while attempting to symlink " "the latest %s" % latest_log
        )


def setup_logs_dir(log_dir):
    if not os.path.exists(log_dir):
        safe_mkdirs(log_dir, 0o777)


def setup_log_file(log_file):
    setup_logs_dir(os.path.dirname(log_file))


@contextmanager
def capture_log_into_file(log_file, formatter, level):
    setup_log_file(log_file)

    handler = logging.FileHandler(filename=log_file, encoding="utf-8")
    handler.setFormatter(formatter)
    handler.setLevel(level)

    try:
        logging.root.addHandler(handler)
        yield handler
    finally:
        try:
            logging.root.removeHandler(handler)
            handler.close()
        except Exception:
            logger.error("Failed to close file handler for  log %s", log_file)


@contextmanager
def override_log_formatting(log_format):
    original_formatters = [handler.formatter for handler in logger.root.handlers]
    try:
        raw_formatter = logging.Formatter(log_format)
        for handler in logger.root.handlers:
            handler.setFormatter(raw_formatter)

        yield
    finally:
        for handler, formatter in zip(logger.root.handlers, original_formatters):
            handler.setFormatter(formatter)


def raw_log_formatting():
    return override_log_formatting("%(message)s")


class StreamLogWriter(object):
    encoding = False

    """
    Allows to redirect stdout and stderr to logger
    """

    def __init__(self, logger, level):
        """
        :param log: The log level method to write to, ie. log.debug, log.warning
        :return:
        """
        self.logger = logger
        self.level = level
        self._buffer = str()

    def write(self, message):
        """
        Do whatever it takes to actually log the specified logging record
        :param message: message to log
        """
        if not message.endswith("\n"):
            self._buffer += message
        else:
            self._buffer += message
            self.logger.log(self.level, self._buffer.rstrip())
            self._buffer = str()

    def flush(self):
        """
        Ensure all logging output has been flushed
        """
        if len(self._buffer) > 0:
            self.logger.log(self.level, self._buffer)
            self._buffer = str()

    def isatty(self):
        """
        Returns False to indicate the fd is not connected to a tty(-like) device.
        For compatibility reasons.
        """
        return False


@contextmanager
def redirect_stdout(logger, level):
    writer = StreamLogWriter(logger, level)
    original = sys.stdout
    try:
        sys.stdout = writer
        yield
    finally:
        sys.stdout = original


@contextmanager
def redirect_stderr(logger, level):
    writer = StreamLogWriter(logger, level)
    original = sys.stderr
    try:
        sys.stderr = writer
        yield
    finally:
        sys.stderr = original


def set_module_logging_to_debug(modules):
    for m in modules:
        logging.getLogger(m.__name__).setLevel(logging.DEBUG)


class TaskContextFilter(logging.Filter):
    """
    adding task task variable to every record
    """

    task = "main"

    def filter(self, record):
        if self.task is not None:
            record.task = self.task
        return True

    @classmethod
    @contextmanager
    def task_context(cls, task_id):
        original_task = cls.task
        cls.task = task_id
        yield cls
        cls.task = original_task
