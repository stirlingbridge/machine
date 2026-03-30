import click
import json

from machine.log import output as log_output
from machine.types import MainCmdCtx


def print_normal(domains):
    for domain in domains:
        log_output(f"{domain}")


def print_json(domains):
    log_output(json.dumps(domains))


@click.command(help="List dns domains")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.pass_context
def command(context, output):
    command_context: MainCmdCtx = context.obj
    provider = command_context.provider
    domains = provider.list_domains()
    if output == "json":
        print_json(domains)
    else:
        print_normal(domains)
