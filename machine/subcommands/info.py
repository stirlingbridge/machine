import click

from machine.config import resolve_config_file_path
from machine.constants import default_session_id_file_path
from machine.log import output
from machine.providers import KNOWN_PROVIDERS
from machine.types import MainCmdCtx


@click.command(help="Show diagnostic information about the current configuration")
@click.pass_context
def command(context):
    command_context: MainCmdCtx = context.obj
    config_file_option = context.parent.params.get("config_file")
    config_file = resolve_config_file_path(config_file_option)

    output(f"Config file: {config_file}")
    output("")
    output("Config file contents:")
    with open(config_file, "r") as f:
        output(f.read().rstrip())

    output("")
    output(f"Session ID file: {default_session_id_file_path}")
    output(f"Session ID: {command_context.session_id}")

    output("")
    output(f"Supported providers: {', '.join(KNOWN_PROVIDERS)}")
    output(f"Active provider: {command_context.config.provider_name}")
