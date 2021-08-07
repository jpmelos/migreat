"""Migration tooling."""
import hashlib
import logging
import operator
import re

import psycopg2

logger = logging.getLogger(__name__)

MIGRATION_PREFIX_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}$")
MIGRATION_NAME_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{2}-[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]\.sql$"
)


class MigrationException(Exception):
    """
    Raise when an error related to parsing and running migrations happens.
    """


class MigrationsTableDoesNotExist(MigrationException):
    """Raise when the migrations table does not exist in the database."""


class InvalidMigrationNameOrPrefix(MigrationException):
    """Raise when a prefix or a name of a migration is invalid."""

    def __init__(self, migration_name):
        """Raise when a prefix or a name of a migration is invalid.

        Args:
            migration_name: The invalid migration name or prefix.
        """
        self.migration_name = migration_name

        super().__init__(
            f"Invalid migration name or prefix: {migration_name}."
        )


class RepeatedMigrationSequenceNumber(MigrationException):
    """
    Raise when there are multiple migrations with the same sequence number.
    """

    def __init__(self, sequence_number):
        """
        Raise when there are multiple migrations with the same sequence number.

        Args:
            sequence_number: The sequence number that has repeated occurrences.
        """
        self.sequence_number = sequence_number

        super().__init__(
            f"Sequence number {sequence_number} has multiple occurrences."
        )


class InvalidMigrationHash(MigrationException):
    """Raise when a migration hash in the database doesn't match the files."""

    def __init__(self, migration_name, actual_hash, expected_hash):
        """Raise when a migration hash in the database doesn't match the files.

        Args:
            migration_name: The name of the migration whose hashes don't match.
            actual_hash: The hash computed from the files in disk.
            expected_hash: The expected hash from the database.
        """
        self.migration_name = migration_name
        self.actual_hash = actual_hash
        self.expected_hash = expected_hash

        super().__init__(
            f"Migration {migration_name} has different hash from file in disk"
            f" from hash found in the database: {actual_hash} !="
            f" {expected_hash}."
        )


class NoRollbackMigration(MigrationException):
    """Raise when there is no rollback for a migration selected to rollback."""

    def __init__(self, migration_name):
        """
        Raise when there is no rollback for a migration selected to rollback.

        Args:
            migration_name: The name of the migration that doesn't have a
                rollback.
        """
        self.migration_name = migration_name

        super().__init__(
            f"Migration {migration_name} doesn't have rollback code"
        )


class DropUsersForeignKeyDependencyAttempt(MigrationException):
    """Raise when the users foreign key is blocking a rollback."""


def _get_migration_sequence_number(migration_name):
    """Return the sequence number of a migration from its name.

    Args:
        migration_name: The prefix or migration name from which we will extract
            the sequence number.

    Returns:
        The sequence number.
    """
    invalid_name_or_prefix = not (
        MIGRATION_PREFIX_REGEX.fullmatch(migration_name)
        or MIGRATION_NAME_REGEX.fullmatch(migration_name)
    )
    if invalid_name_or_prefix:
        raise InvalidMigrationNameOrPrefix(migration_name)
    return int(migration_name[:13].replace("-", ""))


class Migration:
    """Represent a migration."""

    def __init__(self, path):
        """Represent a migration.

        Args:
            path: The path of the forward migration file.
        """
        if not MIGRATION_NAME_REGEX.fullmatch(path.name):
            raise InvalidMigrationNameOrPrefix(path.name)

        self.path = path

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def name(self):
        """The name of the forward migration file.

        Returns:
            The name of the forward migration file.
        """
        return self.path.name

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def rollback_name(self):
        """The name of the rollback migration file.

        Returns:
            The name of the rollback migration file.
        """
        return self.path.name[:-4] + ".rollback.sql"

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def sequence_number(self):
        """The migration sequence number.

        Returns:
            The migration name sequence number.
        """
        return _get_migration_sequence_number(self.name)

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def rollback_path(self):
        """The path to the rollback migration file.

        Returns:
            The path to the rollback migration file.
        """
        return self.path.parent / self.rollback_name

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def code(self):
        """The forward migration code.

        Returns:
            The forward migration code.
        """
        with self.path.open() as fp:
            return fp.read()

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def rollback_code(self):
        """The rollback migration code.

        Returns:
            The rollback migration code.
        """
        if self.rollback_path.exists() and self.rollback_path.is_file():
            with self.rollback_path.open() as fp:
                return fp.read()
        return None

    # TODO Can be @cached_property once we drop Pythyon 3.7
    @property
    def hash(self):  # noqa: A003
        """The hash for a migration.

        We store migration hashes in the database to make sure we are running
        new migrations against a database in a state we know, and we are
        rolling back migrations whose code hasn't changed.

        Returns:
            The migration hash.
        """
        code_to_hash = self.code + (self.rollback_code or "")
        return hashlib.sha1(code_to_hash.encode("utf-8")).digest().hex()


def _table_exists(cursor, table_name):
    """Return whether a table exists among the visible tables to the cursor.

    Args:
        cursor: The cursor to use to verify the existence of the table.
        table_name: The name of the table we want to verify.

    Returns:
        Whether the table exists.
    """
    # TODO Investigate why `n.oid` and `c.oid`. Can this be simpler?
    cursor.execute(
        """
            SELECT relname
                FROM pg_class AS c
                JOIN pg_namespace AS n
                    ON n.oid = c.relnamespace
                WHERE
                    pg_catalog.pg_table_is_visible(c.oid)
                    AND relname = %s;
        """,
        (table_name,),
    )
    return bool(cursor.fetchone())


def create_migrations_table(
    cursor_factory, cursor_factory_args=None, cursor_factory_kwargs=None
):
    """Create the migrations table.

    This table stores information about previously run migrations for log
    purposes and to allow reliable rollback operations.

    Args:
        cursor_factory: The DBAPI cursor factory to use to obtain a cursor to
            the database.
        cursor_factory_args: Arguments to pass to the cursor factory.
        cursor_factory_kwargs: Keyword arguments to pass to the cursor factory.
    """
    if cursor_factory_args is None:  # pragma: no branch
        cursor_factory_args = []
    if cursor_factory_kwargs is None:  # pragma: no branch
        cursor_factory_kwargs = {}

    with cursor_factory(
        *cursor_factory_args, **cursor_factory_kwargs
    ) as cursor:
        try:
            cursor.execute(
                """
                    CREATE TABLE migreat_migrations (
                        id SERIAL PRIMARY KEY,
                        applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        user_id INTEGER NOT NULL,
                        name VARCHAR(250) NOT NULL UNIQUE
                            CHECK (CHAR_LENGTH(name) > 0),
                        hash VARCHAR(40) NOT NULL
                            CHECK (CHAR_LENGTH(hash) = 40)
                    );
                """
            )
            logger.info("Created migrations table.")
        except psycopg2.errors.DuplicateTable:
            logger.info("Migrations table already exists.")


def drop_migrations_table(
    cursor_factory, cursor_factory_args=None, cursor_factory_kwargs=None
):
    """Drop the migrations table.

    Args:
        cursor_factory: The DBAPI cursor factory to use to obtain a cursor to
            the database.
        cursor_factory_args: Arguments to pass to the cursor factory.
        cursor_factory_kwargs: Keyword arguments to pass to the cursor factory.
    """
    if cursor_factory_args is None:  # pragma: no branch
        cursor_factory_args = []
    if cursor_factory_kwargs is None:  # pragma: no branch
        cursor_factory_kwargs = {}

    with cursor_factory(
        *cursor_factory_args, **cursor_factory_kwargs
    ) as cursor:
        try:
            cursor.execute("DROP TABLE migreat_migrations;")
            logger.info("Dropped migrations table.")
        except psycopg2.errors.UndefinedTable:
            logger.info("Migrations table doesn't exist.")


def create_user_id_foreign_key(
    users_table,
    user_id_field,
    cursor_factory,
    cursor_factory_args=None,
    cursor_factory_kwargs=None,
):
    """Make `user_id` field in the migrations table refer to an actual user ID.

    Args:
        users_table: The name of the users table.
        user_id_field: The name of the user ID field.
        cursor_factory: The DBAPI cursor factory to use to obtain a cursor to
            the database.
        cursor_factory_args: Arguments to pass to the cursor factory.
        cursor_factory_kwargs: Keyword arguments to pass to the cursor factory.
    """
    if cursor_factory_args is None:  # pragma: no branch
        cursor_factory_args = []
    if cursor_factory_kwargs is None:  # pragma: no branch
        cursor_factory_kwargs = {}

    with cursor_factory(
        *cursor_factory_args, **cursor_factory_kwargs
    ) as cursor:
        try:
            cursor.execute(
                f"""
                    ALTER TABLE migreat_migrations
                        ADD CONSTRAINT migreat_migrations_user_id_fk
                            FOREIGN KEY (user_id)
                            REFERENCES {users_table} ({user_id_field});
                """
            )
            logger.info("Created the user_id foreign key constraint.")
        except psycopg2.errors.DuplicateObject:
            logger.info("user_id foreign key constraint already exists.")


def drop_user_id_foreign_key(
    cursor_factory, cursor_factory_args=None, cursor_factory_kwargs=None
):
    """Drop the user_id foreign key.

    Preprocesses the cursor args and kwargs.

    Args:
        cursor_factory: The DBAPI cursor factory to use to obtain a cursor to
            the database.
        cursor_factory_args: Arguments to pass to the cursor factory.
        cursor_factory_kwargs: Keyword arguments to pass to the cursor factory.
    """
    if cursor_factory_args is None:  # pragma: no branch
        cursor_factory_args = []
    if cursor_factory_kwargs is None:  # pragma: no branch
        cursor_factory_kwargs = {}

    with cursor_factory(
        *cursor_factory_args, **cursor_factory_kwargs
    ) as cursor:
        _drop_user_id_foreign_key(cursor)


def _drop_user_id_foreign_key(cursor):
    """Drop the user_id foreign key.

    Preprocesses the cursor args and kwargs.

    Args:
        cursor: The cursor that will be used for any database queries.
    """
    try:
        cursor.execute(
            """
                ALTER TABLE migreat_migrations
                    DROP CONSTRAINT migreat_migrations_user_id_fk;
            """
        )
        logger.info("Dropped the user_id foreign key constraint.")
    except psycopg2.errors.UndefinedObject:
        logger.info("user_id foreign key constraint doesn't exist.")


def _has_run_before(cursor, migration):
    """Return whether a migration has run before.

    Args:
        cursor: The cursor that will be used for any database queries.
        migration: The migration to be checked.

    Returns:
        Whether the migration has run before or not.
    """
    cursor.execute(
        """
            SELECT hash
                FROM migreat_migrations
                WHERE name = %s;
        """,
        (migration.name,),
    )
    record = cursor.fetchone()
    if not record:
        return False

    migration_hash = record[0]
    if migration_hash != migration.hash:
        raise InvalidMigrationHash(
            migration.name, migration.hash, migration_hash
        )

    return True


def _run_migration_code(cursor, user_id, migration, rollback):
    """Run a migration.

    Checks for known or expected errors and raises specific exceptions to each
    of them.

    Args:
        cursor: The cursor to be used to make any database queries.
        user_id: The ID of the user that is running the migration.
        migration: The migration to run.
        rollback: Whether this is a rollback or not.
    """
    if rollback:
        if migration.rollback_code is None:
            raise NoRollbackMigration(migration.name)

        if migration.rollback_code:
            try:
                cursor.execute(migration.rollback_code)
            except psycopg2.errors.DependentObjectsStillExist as e:
                if "migreat_migrations_user_id_fk" in e.diag.message_detail:
                    raise DropUsersForeignKeyDependencyAttempt
                raise  # pragma: no cover
        cursor.execute(
            """
                DELETE FROM migreat_migrations
                    WHERE name = %s;
            """,
            (migration.name,),
        )
    else:
        if migration.code:
            cursor.execute(migration.code)
        cursor.execute(
            """
                INSERT INTO migreat_migrations
                    (user_id, name, hash)
                    VALUES
                        (%s, %s, %s);
            """,
            (user_id, migration.name, migration.hash),
        )


def _run_migration(cursor, user_id, migration, rollback):
    """Run a migration's code.

    Args:
        cursor: The cursor to be used to make any database queries.
        user_id: The ID of the user that is running the migration.
        migration: The migration to run.
        rollback: Whether this is a rollback or not.
    """
    has_run_before = _has_run_before(cursor, migration)
    should_run = has_run_before == rollback

    if rollback:
        name = migration.rollback_name
    else:
        name = migration.name

    if should_run:
        logger.info(f"Running {name}.")
        try:
            _run_migration_code(cursor, user_id, migration, rollback)
        except DropUsersForeignKeyDependencyAttempt:
            logger.info(
                f"Failed to run {name} because of the users foreign key, will "
                f"drop that and retry."
            )
            raise
        except Exception:  # noqa: B902
            logger.info(f"Failed to run {name}.")
            raise
        else:
            logger.info(f"Ran {name}.")
    else:
        logger.info(f"{name} has already run.")


def run_migrations(
    user_id,
    migrations_dir,
    cursor_factory,
    cursor_factory_args=None,
    cursor_factory_kwargs=None,
    last_migration=None,
    rollback=False,
):
    """Run all the migrations selected.

    The expected format for migration names is:

    `%Y-%m-%d-%n-<name>.<extension>`

    In which `%Y-%m-%d` is the date in which the migration was merged into
    the repository in `datetime.datetime.strftime` format, and `%n` is a
    serial number used to allow many migrations to be merged in the same
    day. The sequence number is a 2-digit number and starts at `01`.

    The name can be any string of any length containing `[A-Za-z0-9-]`, as
    long as the first and last characters are not `-`.

    The extension right now can be `.sql` for the forward and
    `.rollback.sql` for the rollback code. Other extensions, like `.py`,
    may be supported in the future.

    If it's a forward migration operation, all migrations up to
    `migration_name` will be run. If it's a rollback migration operation, all
    migrations back up to `migration_name` will be run.

    Args:
        user_id: The ID of the user running the migrations.
        migrations_dir: The directory where we can find the migrations.
        cursor_factory: The DBAPI cursor factory to use to obtain a cursor to
            the database.
        cursor_factory_args: Arguments to pass to the cursor factory.
        cursor_factory_kwargs: Keyword arguments to pass to the cursor factory.
        last_migration: The migration file prefix or full name we want to run
            up to.
        rollback: Whether you want to perform a rollback operation up to the
            migration specified instead of an update.
    """
    if cursor_factory_args is None:  # pragma: no branch
        cursor_factory_args = []
    if cursor_factory_kwargs is None:  # pragma: no branch
        cursor_factory_kwargs = {}

    logger.info("Starting migration procedure.")

    if last_migration:
        sequence_end = _get_migration_sequence_number(last_migration)
        if rollback:
            logger.info(f"Running migrations back up to {last_migration}.")
        else:
            logger.info(f"Running migrations up to {last_migration}.")
    else:
        sequence_end = None

    # Get all migrations ordered by sequence number.
    migration_paths = [
        migration_file
        for migration_file in migrations_dir.iterdir()
        if migration_file.is_file()
        and migration_file.name.endswith(".sql")
        and not migration_file.name.endswith(".rollback.sql")
    ]
    migrations = sorted(
        (Migration(path) for path in migration_paths),
        key=operator.attrgetter("sequence_number"),
        reverse=rollback,
    )

    if not migrations:
        logger.info("Done.")
        return

    # Verify all sequence numbers are unique.
    set_of_sequence_numbers = {
        migration.sequence_number for migration in migrations
    }
    if len(migrations) != len(set_of_sequence_numbers):
        seen_sequence_numbers = set()
        for migration in migrations:  # pragma: no branch, len(migrations) > 0
            if migration.sequence_number in seen_sequence_numbers:
                raise RepeatedMigrationSequenceNumber(
                    migration.sequence_number
                )
            seen_sequence_numbers.add(migration.sequence_number)

    # If specified a stop, deselect the migrations that shouldn't be applied.
    if sequence_end:
        if rollback:
            migrations = list(
                filter(lambda m: m.sequence_number >= sequence_end, migrations)
            )
        else:
            migrations = list(
                filter(lambda m: m.sequence_number <= sequence_end, migrations)
            )

    logger.info(f"Found {len(migrations)} migrations.")

    with cursor_factory(
        *cursor_factory_args, **cursor_factory_kwargs
    ) as cursor:
        if not _table_exists(cursor, "migreat_migrations"):
            raise MigrationsTableDoesNotExist

    # Run migrations.
    for migration in migrations:
        try:
            with cursor_factory(
                *cursor_factory_args, **cursor_factory_kwargs
            ) as cursor:
                _run_migration(cursor, user_id, migration, rollback)
        except DropUsersForeignKeyDependencyAttempt:
            with cursor_factory(
                *cursor_factory_args, **cursor_factory_kwargs
            ) as cursor:
                _drop_user_id_foreign_key(cursor)
                _run_migration(cursor, user_id, migration, rollback)

    logger.info("Done.")
