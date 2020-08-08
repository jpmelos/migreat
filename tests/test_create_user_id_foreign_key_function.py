import psycopg2
import pytest

from migreat import create_user_id_foreign_key
from tests.fakepkg.postgresql import atomic


def test_it_creates_the_foreign_key(_migrations):
    create_user_id_foreign_key(
        cursor_factory=atomic, users_table="users", user_id_field="id",
    )
    with atomic() as cursor:
        cursor.execute(
            """
                INSERT INTO migreat_migrations
                    (applied_at, user_id, name, hash)
                VALUES
                    (NOW(), %s, %s, %s);
            """,
            ("1", "2020-01-01-01-migration-1.sql", "a" * 40),
        )
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cursor.execute(
                """
                    INSERT INTO migreat_migrations
                        (applied_at, user_id, name, hash)
                    VALUES
                        (NOW(), %s, %s, %s);
                """,
                ("2", "2020-01-01-01-migration-2.sql", "a" * 40),
            )


def test_it_does_nothing_if_foreign_key_already_exists(_migrations):
    create_user_id_foreign_key(
        cursor_factory=atomic, users_table="users", user_id_field="id",
    )
    create_user_id_foreign_key(
        cursor_factory=atomic, users_table="users", user_id_field="id",
    )
    with atomic() as cursor:
        cursor.execute(
            """
                INSERT INTO migreat_migrations
                    (applied_at, user_id, name, hash)
                VALUES
                    (NOW(), %s, %s, %s);
            """,
            ("1", "2020-01-01-01-migration-1.sql", "a" * 40),
        )
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cursor.execute(
                """
                    INSERT INTO migreat_migrations
                        (applied_at, user_id, name, hash)
                    VALUES
                        (NOW(), %s, %s, %s);
                """,
                ("2", "2020-01-01-01-migration-2.sql", "a" * 40),
            )
