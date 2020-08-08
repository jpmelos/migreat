from migreat import _table_exists, drop_migrations_table
from tests.fakepkg.postgresql import atomic


def test_it_creates_the_migrations_table(_migrations_table):
    drop_migrations_table(cursor_factory=atomic)
    with atomic() as cursor:
        assert not _table_exists(cursor, "migreat_migrations")


def test_it_does_nothing_if_migrations_table_already_exists():
    drop_migrations_table(cursor_factory=atomic)
    with atomic() as cursor:
        assert not _table_exists(cursor, "migreat_migrations")
