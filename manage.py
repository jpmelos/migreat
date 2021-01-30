import shlex
import subprocess
import sys

import click

PYTHON_VERSIONS = ["3.7", "3.8", "3.9"]


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
        shlex.split(command),
        input=input_,
        text=True,
        env=env,
        **kwargs,
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


@manage.command(name="build")
@click.option("--python-version", default="__all__")
@click.option("--no-cache", is_flag=True)
def build_command(python_version, no_cache):
    """Builds the test containers.

    Args:
        python_version: The Python version to use to build the container.
        no_cache: If True, we won't use the build cache in this run.
    """
    if python_version != "__all__" and python_version not in PYTHON_VERSIONS:
        raise Exception("Unsupported Python version.")

    if python_version == "__all__":
        python_versions = PYTHON_VERSIONS
    else:
        python_versions = [python_version]

    kwargs = []
    if no_cache:
        kwargs.append("--no-cache")
    kwargs = " ".join(kwargs)

    for python_version in python_versions:
        _run(
            f"docker build"
            f" {kwargs}"
            f" -t migreat-{python_version}"
            f" -f {python_version}.Dockerfile"
            f" .",
        )


@manage.command(context_settings={"ignore_unknown_options": True})
@click.pass_context
@click.option("--python-version", default="__all__")
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test(ctx, python_version, pytest_args):
    """Runs the automated test suite inside a container."""
    if python_version != "__all__" and python_version not in PYTHON_VERSIONS:
        raise Exception("Unsupported Python version.")

    if python_version == "__all__":
        python_versions = PYTHON_VERSIONS
    else:
        python_versions = [python_version]

    for python_version in python_versions:
        ctx.invoke(
            build_command,
            python_version=python_version,
            no_cache=False,
        )

        _run("docker network create migreat_network")

        _run(
            "docker run"
            " -d"
            " --net migreat_network"
            " --name migreat_test_db"
            " -e POSTGRES_USER=migreat"
            " -e POSTGRES_PASSWORD=migreat"
            " postgres:13",
        )

        _run(
            f"docker run"
            f" --rm"
            f" --net migreat_network"
            f" -e DB_HOST=migreat_test_db"
            f" -e DB_PORT=5432"
            f" -e DB_USER=migreat"
            f" -e DB_PASS=migreat"
            f" -e PYTHON_PATH=."
            f" migreat-{python_version}"
            f" {' '.join(list(pytest_args))}",
        )


if __name__ == "__main__":
    manage()
