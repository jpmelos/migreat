from migreat import _table_exists, create_migrations_table
from tests.fakepkg.postgresql import atomic


def test_it_creates_the_migrations_table():
    create_migrations_table(cursor_factory=atomic)
    with atomic() as cursor:
        assert _table_exists(cursor, "migreat_migrations")


def test_it_does_nothing_if_migrations_table_already_exists():
    create_migrations_table(cursor_factory=atomic)
    create_migrations_table(cursor_factory=atomic)
    with atomic() as cursor:
        assert _table_exists(cursor, "migreat_migrations")
