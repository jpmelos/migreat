import pytest

from migreat import (
    InvalidMigrationHash,
    InvalidMigrationNameOrPrefix,
    MigrationsTableDoesNotExist,
    NoRollbackMigration,
    RepeatedMigrationSequenceNumber,
    _table_exists,
    create_user_id_foreign_key,
    run_migrations,
)
from tests.fakepkg.postgresql import atomic


@pytest.fixture()
def migrations_empty_dir(this_path):
    return this_path / "migrations_empty"


@pytest.fixture()
def repeated_sq_migrations_dir(this_path):
    return this_path / "migrations_repeated_sq"


@pytest.fixture()
def no_rollback_migrations_dir(this_path):
    return this_path / "migrations_no_rollback"


@pytest.fixture()
def invalid_name_migrations_dir(this_path):
    return this_path / "migrations_invalid_name"


def test_it_runs_forward(_migrations_table, migrations_dir):
    run_migrations(
        user_id=42, migrations_dir=migrations_dir, cursor_factory=atomic
    )
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


def test_it_runs_forward_up_to_a_given_point(
    _migrations_table, migrations_dir
):
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
        last_migration="2020-01-01-01",
    )
    with atomic() as cursor:
        assert _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")

        cursor.execute("SELECT user_id, name FROM migreat_migrations;")
        records = cursor.fetchall()
        assert len(records) == 1
        assert records[0][0] == 1
        assert records[0][1] == "2020-01-01-01-create-users-table.sql"

        cursor.execute("SELECT username FROM users;")
        assert cursor.fetchone()[0] == "migreat"


def test_it_runs_forward_from_previously_ran_migrations(
    _migrations_table, migrations_dir
):
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
        last_migration="2020-01-01-01",
    )
    run_migrations(
        user_id=1, migrations_dir=migrations_dir, cursor_factory=atomic
    )
    with atomic() as cursor:
        assert _table_exists(cursor, "migreat_migrations")
        assert _table_exists(cursor, "users")
        assert _table_exists(cursor, "customers")

        cursor.execute("SELECT user_id, name FROM migreat_migrations;")
        records = cursor.fetchall()
        assert len(records) == 3
        assert records[0][0] == 1
        assert records[0][1] == "2020-01-01-01-create-users-table.sql"
        assert records[1][0] == 1
        assert records[1][1] == "2020-01-01-02-empty-migration.sql"
        assert records[2][0] == 1
        assert records[2][1] == "2020-01-02-01-create-customers-table.sql"

        cursor.execute("SELECT username FROM users;")
        assert cursor.fetchone()[0] == "migreat"

        cursor.execute("SELECT name FROM customers;")
        assert not cursor.fetchall()


def test_it_runs_when_no_migrations_left_to_run(_migrations, migrations_dir):
    run_migrations(
        user_id=1, migrations_dir=migrations_dir, cursor_factory=atomic
    )
    with atomic() as cursor:
        assert _table_exists(cursor, "migreat_migrations")
        assert _table_exists(cursor, "users")
        assert _table_exists(cursor, "customers")

        cursor.execute("SELECT user_id, name FROM migreat_migrations;")
        records = cursor.fetchall()
        assert len(records) == 3
        assert records[0][0] == 1
        assert records[0][1] == "2020-01-01-01-create-users-table.sql"
        assert records[1][0] == 1
        assert records[1][1] == "2020-01-01-02-empty-migration.sql"
        assert records[2][0] == 1
        assert records[2][1] == "2020-01-02-01-create-customers-table.sql"

        cursor.execute("SELECT username FROM users;")
        assert cursor.fetchone()[0] == "migreat"

        cursor.execute("SELECT name FROM customers;")
        assert not cursor.fetchall()


def test_it_rolls_back(_migrations, migrations_dir):
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
        rollback=True,
    )
    with atomic() as cursor:
        assert not _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")


def test_it_rolls_back_up_to_a_given_point(_migrations_table, migrations_dir):
    run_migrations(
        user_id=1, migrations_dir=migrations_dir, cursor_factory=atomic
    )
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
        last_migration="2020-01-01-02",
        rollback=True,
    )
    with atomic() as cursor:
        assert _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")

        cursor.execute("SELECT user_id, name FROM migreat_migrations;")
        records = cursor.fetchall()
        assert len(records) == 1
        assert records[0][0] == 1
        assert records[0][1] == "2020-01-01-01-create-users-table.sql"

        cursor.execute("SELECT username FROM users;")
        assert cursor.fetchone()[0] == "migreat"


def test_it_rolls_back_when_users_foreign_key_exists(
    _migrations, migrations_dir
):
    create_user_id_foreign_key(
        cursor_factory=atomic, users_table="users", user_id_field="id"
    )
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
        rollback=True,
    )
    with atomic() as cursor:
        assert not _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")


def test_it_does_nothing_rollback_when_no_migrations_ran(
    _migrations_table, migrations_dir
):
    run_migrations(
        user_id=1,
        migrations_dir=migrations_dir,
        cursor_factory=atomic,
        rollback=True,
    )
    with atomic() as cursor:
        assert not _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")


def test_it_does_nothing_when_no_migrations_exist(
    _migrations_table, migrations_empty_dir
):
    run_migrations(
        user_id=1, migrations_dir=migrations_empty_dir, cursor_factory=atomic
    )
    with atomic() as cursor:
        assert not _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")


def test_it_does_nothing_rollback_when_no_migrations_exist(
    _migrations_table, migrations_empty_dir
):
    run_migrations(
        user_id=1,
        migrations_dir=migrations_empty_dir,
        cursor_factory=atomic,
        rollback=True,
    )
    with atomic() as cursor:
        assert not _table_exists(cursor, "users")
        assert not _table_exists(cursor, "customers")


def test_it_raises_when_there_are_repeated_sequence_numbers(
    _migrations_table, repeated_sq_migrations_dir
):
    with pytest.raises(RepeatedMigrationSequenceNumber):
        run_migrations(
            user_id=1,
            migrations_dir=repeated_sq_migrations_dir,
            cursor_factory=atomic,
        )


def test_it_raises_if_migrations_table_doesnt_exist(migrations_dir):
    with pytest.raises(MigrationsTableDoesNotExist):
        run_migrations(
            user_id=1, migrations_dir=migrations_dir, cursor_factory=atomic
        )


def test_it_raises_when_migration_hash_doesnt_match(
    _migrations_table, migrations_dir
):
    run_migrations(
        user_id=1, migrations_dir=migrations_dir, cursor_factory=atomic
    )
    with atomic() as cursor:
        cursor.execute(
            """
                UPDATE migreat_migrations
                    SET hash = %s
                    WHERE name = %s
            """,
            ("a" * 40, "2020-01-01-01-create-users-table.sql"),
        )

    with pytest.raises(InvalidMigrationHash):
        run_migrations(
            user_id=1,
            migrations_dir=migrations_dir,
            cursor_factory=atomic,
            rollback=True,
        )


def test_it_raises_when_trying_to_rollback_no_rollback_migration(
    _migrations_table, no_rollback_migrations_dir
):
    run_migrations(
        user_id=1,
        migrations_dir=no_rollback_migrations_dir,
        cursor_factory=atomic,
    )
    with pytest.raises(NoRollbackMigration):
        run_migrations(
            user_id=1,
            migrations_dir=no_rollback_migrations_dir,
            cursor_factory=atomic,
            rollback=True,
        )


def test_it_raises_when_migration_has_invalid_name(
    _migrations_table, invalid_name_migrations_dir
):
    with pytest.raises(InvalidMigrationNameOrPrefix):
        run_migrations(
            user_id=1,
            migrations_dir=invalid_name_migrations_dir,
            cursor_factory=atomic,
        )


def test_it_raises_when_last_migration_has_invalid_name(
    _migrations_table, migrations_dir
):
    with pytest.raises(InvalidMigrationNameOrPrefix):
        run_migrations(
            user_id=1,
            migrations_dir=migrations_dir,
            cursor_factory=atomic,
            last_migration="2020-01-01",
        )
