import click
import json

from machine.log import fatal_error, output
from machine.types import MainCmdCtx, TAG_MACHINE_TYPE_PREFIX, TAG_MACHINE_SESSION_PREFIX
from machine.util import get_machine_type, is_machine_created, is_same_session, vm_to_json_obj


def print_normal(vms):
    for vm in vms:
        region = vm.region if vm.region else "unknown"
        output(f"{vm.name} ({vm.id}, {region}, {get_machine_type(vm)}): {vm.ip_address}")


def print_quiet(vms):
    for vm in vms:
        output(vm.id)


def print_json(vms):
    output(json.dumps([vm_to_json_obj(v) for v in vms]))


def get_vms(command_context, id=None, name=None, tag=None, type=None, region=None, all=False):
    provider = command_context.provider

    vms = []
    if id:
        vm = provider.get_vm(id)
        if vm:
            vms.append(vm)

    if all:
        vms = provider.list_vms()
    else:
        vms = provider.list_vms(tag=TAG_MACHINE_SESSION_PREFIX + command_context.session_id)

    # we can't combine most filters over the API, so we also filter ourselves
    if name:
        vms = filter(lambda v: v.name == name, vms)

    if tag:
        vms = filter(lambda v: tag in v.tags, vms)

    if type:
        vms = filter(lambda v: TAG_MACHINE_TYPE_PREFIX + type.lower() in v.tags, vms)

    if region:
        vms = filter(lambda v: v.region and region == v.region, vms)

    if not all:
        vms = filter(lambda v: is_machine_created(v) and is_same_session(command_context, v), vms)

    return list(vms)


@click.command(help="List machines")
@click.option("--id", metavar="<MACHINE-ID>", help="Filter by id")
@click.option("--name", "-n", metavar="<MACHINE-NAME>", help="Filter by name")
@click.option("--tag", "-t", metavar="<TAG-TEXT>", help="Filter by tag")
@click.option("--type", "-m", metavar="<MACHINE-TYPE>", help="Filter by type")
@click.option("--region", "-r", metavar="<REGION>", help="Filter by region")
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.option(
    "--all",
    is_flag=True,
    default=False,
    help="All machines, including those not created by this tool or by other sessions",
)
@click.option("--quiet", "-q", is_flag=True, default=False, help="Only display machine IDs")
@click.option(
    "--unique",
    is_flag=True,
    default=False,
    help="Return an error if there is more than one match",
)
@click.pass_context
def command(context, id, name, tag, type, region, all, output, quiet, unique):
    command_context: MainCmdCtx = context.obj

    vms = get_vms(command_context, id, name, tag, type, region, all)
    if unique and len(vms) > 1:
        fatal_error(f"ERROR: --unique match required but {len(vms)} matches found.")

    if output == "json":
        print_json(vms)
    elif quiet:
        print_quiet(vms)
    else:
        print_normal(vms)
