import contextlib
import os

import psycopg2


@contextlib.contextmanager
def atomic():
    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]

    connection = psycopg2.connect(
        f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/migreat_tests"
    )

    try:
        yield connection.cursor()
        connection.commit()
    except Exception:  # noqa: B902
        connection.rollback()
        raise
    finally:
        connection.close()
