
import click
import digitalocean
from machine.types import MainCmdCtx


@click.command(help="List domain records")
@click.argument('zone')
@click.pass_context
def command(context, zone):
    command_context: MainCmdCtx = context.obj
    domain = digitalocean.Domain(token=command_context.config.access_token, name=zone)
    records = domain.get_records()
    for record in records:
        if record.type == "A" or record.type == "AAA":
            print(f"{record.name}")
