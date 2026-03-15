import click
from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="List projects")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    provider = command_context.provider
    projects = provider.list_projects()
    for project in projects:
        output(f"{project}")
