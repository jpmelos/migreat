import shlex
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from migreat import _table_exists
from migreat.__main__ import run
from tests.fakepkg.postgresql import atomic


@pytest.fixture
def _config_file():
    config_file_path = Path(".migreatrc")
    with config_file_path.open("w") as fp:
        fp.write(
            textwrap.dedent(
                """
                    [migreat]
                    user-id=42
                    cursor-factory=tests.fakepkg.postgresql.atomic
                """
            )[1:]
        )

    yield

    config_file_path.unlink()


def _assert_run_migrations_ran():
    with atomic() as cursor:
        assert _table_exists(cursor, "users")
        assert _table_exists(cursor, "customers")

        cursor.execute("SELECT user_id, name FROM migreat_migrations;")
        records = cursor.fetchall()
        assert len(records) == 3
        assert records[0][0] == 42
        assert records[0][1] == "2020-01-01-01-create-users-table.sql"
        assert records[1][0] == 42
        assert records[1][1] == "2020-01-01-02-empty-migration.sql"
        assert records[2][0] == 42
        assert records[2][1] == "2020-01-02-01-create-customers-table.sql"

        cursor.execute("SELECT username FROM users;")
        assert cursor.fetchone()[0] == "migreat"

        cursor.execute("SELECT name FROM customers;")
        assert not cursor.fetchall()


def test_it_calls_run_migrations_correctly(_migrations_table):
    runner = CliRunner()
    result = runner.invoke(
        run,
        shlex.split(
            "--migrations-dir tests/migrations"
            " --user-id 42"
            " --cursor-factory tests.fakepkg.postgresql.atomic"
        ),
    )
    if result.exception:
        raise result.exception

    _assert_run_migrations_ran()


def test_it_calls_run_migrations_correctly_with_config_file(
    _config_file, _migrations_table
):
    runner = CliRunner()
    result = runner.invoke(
        run, shlex.split("--migrations-dir tests/migrations")
    )
    if result.exception:
        raise result.exception

    _assert_run_migrations_ran()


def test_it_raises_when_missing_user_id():
    runner = CliRunner()
    result = runner.invoke(
        run,
        shlex.split(
            "--migrations-dir tests/migrations"
            " --cursor-factory tests.fakepkg.postgresql.atomic"
        ),
    )

    assert isinstance(result.exception, ValueError)


def test_it_raises_when_missing_cursor_factory():
    runner = CliRunner()
    result = runner.invoke(
        run, shlex.split("--migrations-dir tests/migrations --user-id 42")
    )

    assert isinstance(result.exception, ValueError)
