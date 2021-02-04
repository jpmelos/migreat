import os
import shlex
import subprocess
import sys

import click

TEST_ENV = {
    **os.environ,
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "5432",
    "DB_USER": "migreat",
    "DB_PASS": "migreat",
    "PYTHON_PATH": ".",
}


def _run(command, input_=None, pipe_output=False, env=None, check_errors=True):
    """Runs a system command.

    Args:
        command: The command to be run.
        input_: Any input you want to send to the process.
        pipe_output: Whether we should capture stdout and stderr.
        env: Environment variables to send to subprocess.
        check_errors: Whether we should check if errors occurred.

    Returns:
        The completed process object.
    """
    log_message = "*** Running: " + command
    if input_:
        log_message += " // Input: " + input_
    sys.stdout.write(log_message + "\n")

    kwargs = {}
    if pipe_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    process = subprocess.run(
        shlex.split(command), input=input_, text=True, env=env, **kwargs
    )
    if check_errors:
        try:
            process.check_returncode()
        except subprocess.CalledProcessError:
            sys.stdout.write("Command failed\n")
    return process


@click.group()
def manage():
    pass


@manage.command()
@click.option("--check-only", is_flag=True)
def quality(check_only):
    """Checks code quality of the project."""
    if check_only:
        isort_check_only = "--check-only"
        black_check_only = "--check"
    else:
        isort_check_only = ""
        black_check_only = ""

    isort = _run(
        f"isort --profile black {isort_check_only} .", check_errors=False
    ).returncode
    black = _run(
        f"black {black_check_only} --skip-magic-trailing-comma .",
        check_errors=False,
    ).returncode
    flake8 = _run("flake8", check_errors=False).returncode
    if isort or black or flake8:
        sys.exit(1)


@manage.command()
def test_db():
    _run(
        "docker run"
        " -d"
        " --name migreat_test_db"
        " -e POSTGRES_USER=migreat"
        " -e POSTGRES_PASSWORD=migreat"
        " -p 5432:5432"
        " postgres:13"
    )


@manage.command(context_settings={"ignore_unknown_options": True})
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test(pytest_args):
    """Runs the automated test suite."""
    _run(f"coverage run -m pytest {' '.join(list(pytest_args))}", env=TEST_ENV)
    _run("coverage report")
    _run("coverage html")


@manage.command()
def all_tests():
    """Runs the automated test suite."""
    _run("tox", env=TEST_ENV)


if __name__ == "__main__":
    manage()
