import click
import json

from machine.log import output as log_output
from machine.config import get_machines


def print_normal(names):
    for n in names:
        log_output(n)


def print_json(names):
    log_output(json.dumps(names))


@click.command(help="List configured machine types")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.pass_context
def command(context, output):
    config_machines = get_machines()
    names = sorted(config_machines.keys())
    if output == "json":
        print_json(names)
    else:
        print_normal(names)
