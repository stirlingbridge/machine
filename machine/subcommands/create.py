import click
import json
import time

from machine.config import get_machine, has_machine
from machine.di import d
from machine.log import Spinner, fatal_error, info, debug, output as log_output
from machine.provider import CapacityUnavailableError
from machine.types import MainCmdCtx, TAG_MACHINE_CREATED, TAG_MACHINE_TYPE_PREFIX
from machine.cloud_config import get_user_data
from machine.util import vm_to_json_obj

from machine.types import TAG_MACHINE_SESSION_PREFIX


def _validate_dns_zone(provider, dns_zone):
    available_zones = provider.list_domains()
    if dns_zone not in available_zones:
        zones_str = ", ".join(available_zones) if available_zones else "none"
        fatal_error(f"Error: DNS zone '{dns_zone}' not found in {provider.provider_name}. Available zones: {zones_str}")


def _verify_ssh_keys(provider, ssh_key_names):
    for ssh_key_name in ssh_key_names:
        if not provider.get_ssh_key(ssh_key_name):
            fatal_error(f"Error: SSH key '{ssh_key_name}' not found in {provider.provider_name}")


def _get_machine_config(type, initialize):
    # Without --initialize a type may just be a label, but if it is configured we still want its firewall
    if initialize and not type:
        fatal_error("Error: a machine type must be supplied")
    if not type or not (initialize or has_machine(type)):
        return None
    machine_config = get_machine(type)
    if not machine_config:
        fatal_error(f"Error: machine type {type} is not defined")
    return machine_config


def _apply_firewall(provider, type, machine_config):
    # The firewall is attached to the machine type's tag, so it covers every machine of that type
    firewall_name = provider.apply_firewall(
        f"machine-{type.lower()}", TAG_MACHINE_TYPE_PREFIX + type.lower(), machine_config.firewall
    )
    if not d.opt.quiet:
        info(f"Firewall: {firewall_name}")


def _order_by_capacity(provider, choices):
    """Move the (region, size) choices the provider says have no capacity to
    the end, keeping the order of preference otherwise. They are still tried
    last, in case the provider's answer is out of date."""
    if len(choices) < 2:
        return choices
    full = [c for c in choices if provider.has_capacity(*c) is False]
    for region, size in full:
        info(f"Region {region} reports no capacity for size {size}, trying it last")
    return [c for c in choices if c not in full] + full


def _create_with_first_available(provider, regions, sizes, **create_args):
    """Create the VM in the first of `regions`, with the first of `sizes`, that
    the provider has capacity for. Every size is tried in a region before the
    next region: where a machine runs usually matters more than its exact size."""
    choices = [(region, size) for region in regions for size in sizes]
    for region, size in _order_by_capacity(provider, choices):
        try:
            vm = provider.create_vm(region=region, size=size, **create_args)
        except CapacityUnavailableError as e:
            info(str(e))
            continue
        if len(regions) > 1 and not d.opt.quiet:
            info(f"Region: {region}")
        if len(sizes) > 1 and not d.opt.quiet:
            info(f"Size: {size}")
        return vm
    fatal_error(f"Error: no capacity for size {', '.join(sizes)} in any region tried: {', '.join(regions)}")


@click.command(help="Create a machine")
@click.option("--name", "-n", required=True, metavar="<MACHINE-NAME>", help="Name for new machine")
@click.option("--tag", "-t", metavar="<TAG-TEXT>", help="tag to be applied to new machine")
@click.option("--type", "-m", metavar="<MACHINE-TYPE>", help="create a machine of this type")
@click.option(
    "--region",
    "-r",
    metavar="<REGION-CODE>",
    multiple=True,
    help="create a machine in this region (overrides default from config); repeat to give regions to try in order",
)
@click.option(
    "--machine-size",
    "-s",
    metavar="<MACHINE-SLUG>",
    multiple=True,
    help="create a machine of this size (overrides default from config); repeat to give sizes to try in order",
)
@click.option("--image", "-i", metavar="<IMAGE-NAME>", help="create a machine from this image (overrides default from config)")
@click.option("--wait-for-ip/--no-wait-for-ip", default=False)
@click.option(
    "--progress/--no-progress",
    default=False,
    help="Animate a progress indicator while waiting for the machine's IP address",
)
@click.option("--update-dns/--no-update-dns", default=True)
@click.option("--initialize/--no-initialize", default=True)
@click.option("--output", "-o", metavar="<FORMAT>", help="Output format")
@click.pass_context
def command(context, name, tag, type, region, machine_size, image, wait_for_ip, progress, update_dns, initialize, output):
    command_context: MainCmdCtx = context.obj
    config = command_context.config
    provider = command_context.provider

    if update_dns and not config.dns_zone:
        fatal_error("Error: DNS update requested but no zone configured")

    if update_dns and config.dns_zone:
        _validate_dns_zone(provider, config.dns_zone)

    machine_config = _get_machine_config(type, initialize)

    user_data = None
    if initialize:
        fqdn = f"{name}.{config.dns_zone}" if config.dns_zone else None
        user_data = get_user_data(provider, config.ssh_keys, fqdn, machine_config)
        if d.opt.debug:
            info("user-data is:")
            info(user_data)

    # Verify SSH keys exist
    _verify_ssh_keys(provider, config.ssh_keys)

    # Validate what will actually be used, not just what was passed on the
    # command line, so that a bad value in the config file is caught too.
    regions = list(region) if region else config.regions
    image = image if image is not None else config.image
    sizes = list(machine_size) if machine_size else config.machine_sizes

    for r in regions:
        provider.validate_region(r)
    provider.validate_image(image)

    tags = [
        TAG_MACHINE_SESSION_PREFIX + command_context.session_id,
        TAG_MACHINE_CREATED,
    ]
    if type:
        tags.append(TAG_MACHINE_TYPE_PREFIX + type.lower())

    if tag:
        tags.append(tag)

    # Apply the firewall before the machine exists, so it is protected from first boot
    if machine_config and machine_config.firewall:
        _apply_firewall(provider, type, machine_config)

    vm = _create_with_first_available(
        provider,
        regions,
        sizes,
        name=name,
        image=image,
        ssh_key_names=config.ssh_keys,
        tags=tags,
        user_data=user_data,
    )

    if vm.id:
        if output != "json":
            if d.opt.quiet:
                log_output(f"{vm.id}")
            else:
                log_output(f"New machine created with id: {vm.id}")

    # If requested, assign to a specified project
    if config.project:
        provider.assign_to_project(config.project, vm.id)
        if d.opt.verbose:
            info(f"Assigned machine to project: {config.project}")

    # If requested, or if we are going to set a DNS record get the VM's IPv4 address
    # Vultr returns "0.0.0.0" as main_ip while the instance is still pending,
    # so treat that the same as no IP assigned yet.
    ip_address = vm.ip_address if vm.ip_address != "0.0.0.0" else None
    if (wait_for_ip or update_dns) and not ip_address:
        # The spinner and the --verbose progress lines would overwrite each
        # other, so --verbose (which says what is happening in words) wins.
        show_spinner = progress and not d.opt.verbose and not d.opt.quiet
        with Spinner("Waiting for machine IP address", enabled=show_spinner):
            while not ip_address:
                time.sleep(1)
                vm = provider.get_vm(vm.id)
                ip_address = vm.ip_address if vm.ip_address != "0.0.0.0" else None
                if d.opt.verbose:
                    log_output("Waiting for machine IP address")
        if d.opt.quiet:
            info(f"{ip_address}")
        else:
            info(f"IP Address: {ip_address}")

    # If requested, and we have the IP address, create a DNS host record
    if update_dns and ip_address and config.dns_zone:
        zone = config.dns_zone
        host = name
        if d.opt.debug:
            debug(f"Setting host record {host}.{zone} to {ip_address}")
        record = provider.create_dns_record(
            zone=zone,
            record_type="A",
            name=host,
            data=ip_address,
            ttl=60 * 5,
            tag=TAG_MACHINE_CREATED,
        )
        if record:
            if d.opt.verbose:
                info(f"Created DNS record:{record}")
            if not d.opt.quiet:
                info(f"DNS: {host}.{zone}")

    if output == "json":
        log_output(json.dumps(vm_to_json_obj(vm)))
