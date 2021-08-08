"""Run migreat from the command line.

Examples:
    migreat run
        --user-id 42
        --last-migration 2020-01-01-01
        --migrations-dir migrations
        --cursor-factory some.package.atomic
        --cursor-factory-args value1,value2
        --cursor-factory-kwargs key1,value1,key2,value2

        Runs migrations up to 2020-01-01-01 as user with ID 42. Will import
        `some.package.atomic` and use it to get cursors to the database.

    migreat run
        --user-id 42
        --last-migration 2020-01-01-01
        --migrations-dir migrations
        --cursor-factory some.package.atomic
        --cursor-factory-args value1,value2
        --cursor-factory-kwargs key1,value1,key2,value2
        --rollback

        Rolls back migrations up to 2020-01-01-01 as user with ID 42.

    migreat create-migrations-table
        --cursor-factory=some.package.atomic
        --cursor-factory-args value1,value2
        --cursor-factory-kwargs key1,value1,key2,value2
    migreat drop-migrations-table
        --cursor-factory=some.package.atomic
        --cursor-factory-args value1,value2
        --cursor-factory-kwargs key1,value1,key2,value2

        Creates and drops the migrations table.

    migreat create-user-id-foreign-key users id
        --cursor-factory=some.package.atomic
        --cursor-factory-args value1,value2
        --cursor-factory-kwargs key1,value1,key2,value2
    migreat drop-user-id-foreign-key
        --cursor-factory=some.package.atomic
        --cursor-factory-args value1,value2
        --cursor-factory-kwargs key1,value1,key2,value2

        Creates and drops the `user_id` foreign key constraint, referencing
        table `users` on field `id`.

You can create the file `.migreatrc` as:

    [migreat]
    user-id=42
    migrations-dir=migrations
    cursor-factory=some.package.atomic
    cursor-factory-args=value1,value2
    cursor-factory-kwargs=key1,value1,key2,value2
"""
import configparser
import csv
import logging
import os
from importlib import import_module
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple, cast

import click

from migreat import create_migrations_table as create_table
from migreat import create_user_id_foreign_key as create_foreign_key
from migreat import drop_migrations_table as drop_table
from migreat import drop_user_id_foreign_key as drop_foreign_key
from migreat import run_migrations


def _require(value: Any, name: str) -> Any:
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def _get_config() -> Dict[str, Any]:
    config = configparser.ConfigParser()
    config.read(".migreatrc")
    if "migreat" in config:
        return dict(config["migreat"])
    return {}


def _import(import_path: str) -> Any:
    components = import_path.split(".")
    module = ".".join(components[:-1])
    attr_name = components[-1]
    return getattr(import_module(module), attr_name)


def _process_csv_args(args: str) -> List[str]:
    if not args:
        return []
    return list(csv.reader(StringIO(args)))[0]


def _process_csv_kwargs(kwargs: str) -> Dict[str, str]:
    if not kwargs:
        return {}

    keys_and_values = list(csv.reader(StringIO(kwargs)))[0]
    if len(keys_and_values) % 2 != 0:
        raise ValueError("Every key must have a value.")
    return dict(zip(keys_and_values[::2], keys_and_values[1::2]))


def _process_cursor_factory_cli_args(
    cursor_factory: str, cursor_factory_args: str, cursor_factory_kwargs: str
) -> Tuple[Callable, List[str], Dict[str, str]]:
    config = _get_config()

    cursor_factory = _import(
        _require(
            cursor_factory or cast(str, config.get("cursor-factory")),
            "cursor-factory",
        )
    )
    cursor_factory_args = _process_csv_args(
        cursor_factory_args or cast(str, config.get("cursor-factory-args"))
    )
    cursor_factory_kwargs = _process_csv_kwargs(
        cursor_factory_kwargs or cast(str, config.get("cursor-factory-kwargs"))
    )

    return cursor_factory, cursor_factory_args, cursor_factory_kwargs


@click.group()
def cli() -> None:
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))


@cli.command()
@click.option("--migrations-dir")
@click.option("--user-id")
@click.option("--cursor-factory")
@click.option("--cursor-factory-args")
@click.option("--cursor-factory-kwargs")
@click.option("--last-migration")
@click.option("--rollback", is_flag=True)
def run(
    migrations_dir: str,
    user_id: str,
    cursor_factory: str,
    cursor_factory_args: str,
    cursor_factory_kwargs: str,
    last_migration: str,
    rollback: bool,
) -> None:
    config = _get_config()
    migrations_dir = Path(
        migrations_dir
        or cast(str, config.get("migrations-dir"))
        or "migrations"
    )
    user_id = _require(user_id or cast(str, config.get("user-id")), "user-id")
    (
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
    ) = _process_cursor_factory_cli_args(
        cursor_factory, cursor_factory_args, cursor_factory_kwargs
    )

    run_migrations(
        user_id,
        migrations_dir,
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
        last_migration,
        rollback,
    )


@cli.command()
@click.option("--cursor-factory")
@click.option("--cursor-factory-args")
@click.option("--cursor-factory-kwargs")
def create_migrations_table(
    cursor_factory: str, cursor_factory_args: str, cursor_factory_kwargs: str
) -> None:
    (
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
    ) = _process_cursor_factory_cli_args(
        cursor_factory, cursor_factory_args, cursor_factory_kwargs
    )
    create_table(cursor_factory, cursor_factory_args, cursor_factory_kwargs)


@cli.command()
@click.option("--cursor-factory")
@click.option("--cursor-factory-args")
@click.option("--cursor-factory-kwargs")
def drop_migrations_table(
    cursor_factory: str, cursor_factory_args: str, cursor_factory_kwargs: str
) -> None:
    (
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
    ) = _process_cursor_factory_cli_args(
        cursor_factory, cursor_factory_args, cursor_factory_kwargs
    )
    drop_table(cursor_factory, cursor_factory_args, cursor_factory_kwargs)


@cli.command()
@click.argument("users_table")
@click.argument("user_id_field")
@click.option("--cursor-factory")
@click.option("--cursor-factory-args")
@click.option("--cursor-factory-kwargs")
def create_user_id_foreign_key(
    users_table: str,
    user_id_field: str,
    cursor_factory: str,
    cursor_factory_args: str,
    cursor_factory_kwargs: str,
) -> None:
    (
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
    ) = _process_cursor_factory_cli_args(
        cursor_factory, cursor_factory_args, cursor_factory_kwargs
    )
    create_foreign_key(
        users_table,
        user_id_field,
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
    )


@cli.command()
@click.option("--cursor-factory")
@click.option("--cursor-factory-args")
@click.option("--cursor-factory-kwargs")
def drop_user_id_foreign_key(
    cursor_factory: str, cursor_factory_args: str, cursor_factory_kwargs: str
) -> None:
    (
        cursor_factory,
        cursor_factory_args,
        cursor_factory_kwargs,
    ) = _process_cursor_factory_cli_args(
        cursor_factory, cursor_factory_args, cursor_factory_kwargs
    )
    drop_foreign_key(
        cursor_factory, cursor_factory_args, cursor_factory_kwargs
    )


if __name__ == "__main__":
    cli()
