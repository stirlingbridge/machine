
import click
import digitalocean
from machine.types import MainCmdCtx


@click.command(help="List machines")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    manager = digitalocean.Manager(token=command_context.config.access_token)
    droplets = manager.get_all_droplets()
    for droplet in droplets:
        print(f"{droplet.name} ({droplet.id}): {droplet.ip_address}")
