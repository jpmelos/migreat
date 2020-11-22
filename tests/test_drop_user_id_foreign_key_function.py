import pytest

from migreat import create_user_id_foreign_key, drop_user_id_foreign_key
from tests.fakepkg.postgresql import atomic


@pytest.fixture(autouse=True)
def _user_id_foreign_key(_migrations_table, _migrations):
    create_user_id_foreign_key(
        cursor_factory=atomic,
        users_table="users",
        user_id_field="id",
    )


def test_it_drops_the_foreign_key():
    drop_user_id_foreign_key(cursor_factory=atomic)
    with atomic() as cursor:
        cursor.execute(
            """
                INSERT INTO migreat_migrations
                    (user_id, name, hash)
                VALUES
                    (%s, %s, %s);
            """,
            ("2", "2020-01-01-01-migration-2.sql", "a" * 40),
        )


def test_it_does_nothing_if_foreign_key_already_exists():
    drop_user_id_foreign_key(cursor_factory=atomic)
    drop_user_id_foreign_key(cursor_factory=atomic)
    with atomic() as cursor:
        cursor.execute(
            """
                INSERT INTO migreat_migrations
                    (user_id, name, hash)
                VALUES
                    (%s, %s, %s);
            """,
            ("2", "2020-01-01-01-migration-2.sql", "a" * 40),
        )
