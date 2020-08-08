# migreat

A flexible SQL migration runner.

Right now, supports only PostgreSQL, as it's still an experiment. Support for any database with a DBAPI implementation is planned.

## Install

```
pip install migreat
```

## Usage

Migrations are simple SQL files placed inside a directory and following a name pattern. The name pattern is `YEAR-MONTH-DAY-SEQNUM-arbitrary-name.sql`. `YEAR-MONTH-DAY` is the day's date following ISO 8601. The `SEQNUM` is a sequential number for migrations released in the same day. Some valid names:

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

This will run the migrations as user with ID 42, run migrations only up to migration `2020-01-01-01`, it will run the function `yourapp.db.atomic` with no arguments and expect a DBAPI cursor (see tests for an example), and will do it backwards, rolling back all migrations up to `2020-01-01-01`.

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

Clone the source code from GitHub.

Install dependencies (recommended to do this in a virtual environment):

```
pip install -r requirements.txt
```

To spin up a test database in a Docker Engine:

```
docker run -d \
    --name db \
    -p 127.0.0.1:5432:5432 \
    -e POSTGRES_USER=migreat \
    -e POSTGRES_PASSWORD=migreat \
    postgres
```

Set up your environment:

```
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_PASS=migreat
export DB_USER=migreat
```

Run the tests with:

```
coverage run -m pytest
coverage report
```
