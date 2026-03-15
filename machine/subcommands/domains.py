import click
from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="List dns domains")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    provider = command_context.provider
    domains = provider.list_domains()
    for domain in domains:
        output(f"{domain}")
