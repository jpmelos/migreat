# migreat

A flexible SQL migration runner.

Right now, supports only PostgreSQL via `psycopg2`, as it's still an experiment. Support for any database with a DBAPI implementation is planned.

## Install

`migreat` supports Python 3.7, 3.8, and 3.9. Since it currently only supports PostgreSQL via `psycopg2`, it will also be installed.

```
pip install migreat
```

## Mental Model

`migreat` runs SQL migrations with a DB cursor provided by your code via a function, and stores migration metadata in a table with the datetime it was run, the ID of the user who ran it, the name of the migration, and a hash of its contents at the time it was run. The hash of a migration will be checked against if it is ever rolled back, to make sure we are rolling back the same migration that was once run.

## Usage

Migrations are simple SQL files placed inside a directory and following a name pattern. The name pattern is `YEAR-MONTH-DAY-SEQNUM-arbitrary-name.sql`. `YEAR-MONTH-DAY` is the day's date following ISO 8601. The `SEQNUM` is a 2-digit sequential number for migrations released in the same day. Some valid names:

```
2020-01-10-03-create-users-table.sql
2020-03-18-01-remove-foreign-keys-from-audit-tables.sql
```

`migreat` will run the migrations in sequence of date and sequence number.

Create the migrations table:

```
$ migreat create-migrations-table \
    --cursor-factory yourapp.db.atomic
```

Run migrations:

```
$ migreat run \
    --migrations-dir migrations \
    --user-id 42 \
    --last-migration 2020-01-01-01 \
    --cursor-factory yourapp.db.atomic \
    --rollback
```

This will:

- Look for the migrations in directory `migrations` relative to the current working directory;
  - If this is not supplied, the default value will be `migrations`;
- Run the migrations as user with ID 42;
- Run migrations rolling them back, only back up to migration `2020-01-01-01`;
- Run the function `yourapp.db.atomic` with no arguments expecting it to return a DBAPI cursor (see tests for an example).

`migreat` allows you to constrain the user ID to real user IDs you might have in some table in your database. To enable it:

```
$ migreat create-user-id-foreign-key users id \
    --cursor-factory yourapp.db.atomic
```

This will constrain user IDs to values in the column `id` of table `users`.

Finally, you can drop the user ID foreign key constraint:

```
$ migreat drop-user-id-foreign-key \
    --cursor-factory yourapp.db.atomic
```

And drop the migrations table:

```
$ migreat drop-migrations-table \
    --cursor-factory yourapp.db.atomic
```

All above commands also accept:

```
--cursor-factory-args=value1,value2
--cursor-factory-kwargs=key1,value1,key2,value2
```

Values are valid CSV strings and can contain nested commas inside proper delimiters.

## Development

Clone the source code from GitHub, have a Docker Engine reachable, have all supported Python interpreters in your `PATH` (we recommend that you use `pyenv` to manage different Python interpreters and environments) and create a new virtual environment with `poetry install`.

Run the tests with:

```
./run test-db
# Wait for the database to be ready
./run all-tests
```

To run a specific test:

```
./run test-db
# Wait for the database to be ready
./run test <test-address>
```

To make sure your code abides to our quality standards, run:

```
./run quality
```
