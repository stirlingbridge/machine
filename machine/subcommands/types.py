import click

from machine.log import output
from machine.config import get_machines


@click.command(help="List projects")
@click.pass_context
def command(context):
    config_machines = get_machines()
    for m in config_machines:
        output(m)
