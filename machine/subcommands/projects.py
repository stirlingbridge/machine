import click
import json

from machine.log import output as log_output
from machine.types import MainCmdCtx


def print_normal(projects):
    for project in projects:
        log_output(f"{project}")


def print_json(projects):
    log_output(json.dumps(projects))


@click.command(help="List projects")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.pass_context
def command(context, output):
    command_context: MainCmdCtx = context.obj
    provider = command_context.provider
    projects = provider.list_projects()
    if output == "json":
        print_json(projects)
    else:
        print_normal(projects)
