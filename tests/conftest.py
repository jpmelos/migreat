import os
import pathlib

import psycopg2
import pytest

from migreat import create_migrations_table, run_migrations
from tests.fakepkg.postgresql import atomic


@pytest.fixture()
def dbms_connection():
    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]

    connection = psycopg2.connect(
        f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/postgres",
    )
    connection.set_session(autocommit=True)
    yield connection
    connection.close()


@pytest.fixture()
def dbms_cursor(dbms_connection):
    cursor = dbms_connection.cursor()
    yield cursor
    cursor.close()


@pytest.fixture(autouse=True)
def _db(dbms_cursor):
    dbms_cursor.execute("CREATE DATABASE migreat_tests;")
    yield
    dbms_cursor.execute("DROP DATABASE migreat_tests;")


@pytest.fixture()
def this_path(request):
    """The path of the file that contains the currently-running test.

    Args:
        request: The `pytest` request, which is the context of the
            currently-running test.

    Returns:
        The path that contains the currently-running test.
    """
    return pathlib.Path(request.fspath).parent.absolute()


@pytest.fixture()
def migrations_dir(this_path):
    """The migrations directory for tests."""
    return this_path / "migrations"


@pytest.fixture()
def _migrations_table():
    create_migrations_table(cursor_factory=atomic)


@pytest.fixture()
def _migrations(_migrations_table, migrations_dir):
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
    )
