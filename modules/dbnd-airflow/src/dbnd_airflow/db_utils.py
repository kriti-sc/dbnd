import logging
import os
import subprocess
import time
import traceback

from sqlalchemy.engine.url import make_url

from dbnd._core.current import get_databand_context
from dbnd._core.errors import DatabandError


logger = logging.getLogger(__name__)


def get_sqlite_db_location():
    dbnd_context = get_databand_context()
    conn_string = dbnd_context.settings.core.get_sql_alchemy_conn()
    if not conn_string.startswith("sqlite:///"):
        raise DatabandError(
            "We can parse db file name only from sqlite:///..  DBs, got %s"
            % conn_string
        )

    db_location = conn_string.replace("sqlite:///", "")
    return db_location


def dump_postgres(conn_string, dump_file):
    logger.info("backing up postgres DB to %s", dump_file)

    url = make_url(conn_string)

    cmd = [
        "pg_dump",
        "-h",
        url.host,
        "-p",
        str(url.port),
        "-U",
        url.username,
        "-Fc",
        "-f",
        dump_file,
        "-d",
        url.database,
    ]
    logger.info("Running command: %s", subprocess.list2cmdline(cmd))
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password
    subprocess.check_call(args=cmd, env=env)


def remove_listener_by_name(target, identifier, name):
    """
    removes already registered sqlalchemy listener
    use this one only if fn pointer is not accessable (inner function)
    otherwise use regular remove from event api

    Example:
        from airflow import settings
        target = settings.engine
        remove_listener_by_name(target, "engine_connect", "ping_connection")
    """
    import ctypes
    from sqlalchemy import event
    from sqlalchemy.event.registry import _key_to_collection

    all_keys = list(event.registry._key_to_collection.items())
    for key, values in all_keys:

        if key[0] != id(target):
            continue

        if identifier != key[1]:
            continue

        fn = ctypes.cast(key[2], ctypes.py_object).value  # get function by id
        if fn.__name__ != name:
            continue

        event.remove(target, identifier, fn)


def trace_sqlalchemy_query(connection, cursor, query, *_):
    code = "unknown"
    for (file_path, val1, val2, line_contents) in traceback.extract_stack():
        if "airflow" not in file_path:
            continue
        if "utils/sqlalchemy.py" in file_path or "utils/db.py" in file_path:
            continue
        code = str((file_path, val1, val2, line_contents))

    logger.info(
        "\nDBNDSQL QUERY: %s\nDBNDSQL CODE: %s\nDBNDSQL STACK: %s",
        query.replace("\n", "    "),
        code,
        "   ".join(map(str, traceback.extract_stack())),
    )


def profile_before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    conn.info.setdefault("query_start_time", []).append(time.time())
    logger.debug("Start Query: %s", statement)


def profile_after_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    total = time.time() - conn.info["query_start_time"].pop(-1)
    logger.info("Query Complete! %s  --> %f", statement, total)
