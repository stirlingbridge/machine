import click
from machine.log import output
from machine.types import MainCmdCtx


@click.command(help="List ssh keys")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    provider = command_context.provider
    keys = provider.list_ssh_keys()
    for key in keys:
        output(f"{key.id}: {key.name} ({key.fingerprint})")
