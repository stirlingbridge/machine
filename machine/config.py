import ipaddress
import os
import re
from pathlib import Path
from machine.di import d
from machine.factory import yaml
from machine.log import fatal_error, debug
from machine.types import Config, FirewallConfig, FirewallRule, MachineConfig
from machine import constants
from machine.providers import KNOWN_PROVIDERS

_env_var_pattern = re.compile(r"\$\{([^}]+)\}")


def _expand_env_vars(value):
    if isinstance(value, str):

        def _replace(match):
            expr = match.group(1)
            if ":-" in expr:
                var_name, default = expr.split(":-", 1)
                return os.environ.get(var_name, default)
            else:
                if expr not in os.environ:
                    fatal_error(f"Environment variable '{expr}' referenced in config is not set")
                return os.environ[expr]

        return _env_var_pattern.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class _loaded_config:
    c: any = None


def resolve_config_file_path(config_file_name: str) -> str:
    if not config_file_name:
        config_file_name = constants.default_config_file_path
    return str(Path(os.path.expanduser(config_file_name)))


def _load_config_data(config_file_name: str):
    config_path = Path(resolve_config_file_path(config_file_name))
    if not config_path.exists():
        fatal_error(f"Error: Config file: {config_path} not found")
    config = _expand_env_vars(yaml().load(open(config_path, "r")))
    if d.opt.debug:
        debug(f"Loaded config file: {config_path}")
        debug(f"Parsed config: {config}")
    _loaded_config.c = config
    return config


def _require_key(d, key, section_name):
    if key not in d:
        fatal_error(f"Required key '{key}' not found in '{section_name}' section of config file")
    return d[key]


def _get_list(provider_config, key, section_name, noun) -> list:
    """Read a config value that is either a single value (a string) or a list
    of them. Always returns a non-empty list of strings."""
    value = _require_key(provider_config, key, section_name)
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(v) for v in value]
    else:
        fatal_error(f"Config key '{key}' in '{section_name}' section must be a {noun} or a list of {noun}s")
    if not values:
        fatal_error(f"Config key '{key}' in '{section_name}' section must specify at least one {noun}")
    return values


def _get_ssh_keys(provider_config, section_name) -> list:
    """The 'ssh-key' config value: the names of the keys to install."""
    return _get_list(provider_config, "ssh-key", section_name, "name")


def _get_regions(provider_config, section_name) -> list:
    """The 'region' config value: the regions to try, in order of preference."""
    return _get_list(provider_config, "region", section_name, "region")


def _get_machine_sizes(provider_config, section_name) -> list:
    """The 'machine-size' config value: the sizes to try, in order of preference."""
    return _get_list(provider_config, "machine-size", section_name, "size")


_FIREWALL_PROTOCOLS = ("tcp", "udp", "icmp")
_firewall_ports_pattern = re.compile(r"^(all|\d{1,5}(-\d{1,5})?)$")


def _get_firewall_rules(rules, section_name, address_key) -> list:
    if not isinstance(rules, list):
        fatal_error(f"Config key '{section_name}' must be a list of rules")
    ret = []
    for i, rule in enumerate(rules):
        rule_section = f"{section_name}[{i}]"
        if not isinstance(rule, dict):
            fatal_error(f"Firewall rule '{rule_section}' must be a mapping")
        protocol = str(_require_key(rule, "protocol", rule_section)).lower()
        if protocol not in _FIREWALL_PROTOCOLS:
            fatal_error(f"Firewall rule '{rule_section}' protocol must be one of: {', '.join(_FIREWALL_PROTOCOLS)}")
        ports = rule.get("ports")
        if protocol == "icmp":
            if ports is not None:
                fatal_error(f"Firewall rule '{rule_section}' is icmp and cannot specify ports")
        else:
            ports = "all" if ports is None else str(ports)
            if not _firewall_ports_pattern.match(ports):
                fatal_error(f"Firewall rule '{rule_section}' ports must be 'all', a port, or a range like 8000-9000")
        addresses = _require_key(rule, address_key, rule_section)
        if isinstance(addresses, str):
            addresses = [addresses]
        if not isinstance(addresses, list) or not addresses:
            fatal_error(f"Firewall rule '{rule_section}' must specify at least one address in '{address_key}'")
        for address in addresses:
            try:
                ipaddress.ip_network(str(address), strict=False)
            except ValueError:
                fatal_error(f"Firewall rule '{rule_section}' has invalid address: {address}")
        ret.append(FirewallRule(protocol=protocol, ports=ports, addresses=[str(a) for a in addresses]))
    return ret


def _get_firewall(target_config, section_name) -> FirewallConfig:
    """Read a machine type's optional 'firewall' section. Omitting 'outbound'
    allows all outbound traffic; an empty 'outbound' blocks it all."""
    firewall = target_config.get("firewall")
    if firewall is None:
        return None
    section_name = f"{section_name}.firewall"
    if not isinstance(firewall, dict):
        fatal_error(f"Config key '{section_name}' must be a mapping")
    inbound = _get_firewall_rules(firewall.get("inbound") or [], f"{section_name}.inbound", "sources")
    outbound = None
    if "outbound" in firewall:
        outbound = _get_firewall_rules(firewall["outbound"] or [], f"{section_name}.outbound", "destinations")
    return FirewallConfig(inbound=inbound, outbound=outbound)


def get(config_file_name: str) -> Config:
    config = _load_config_data(config_file_name)

    # Auto-detect provider from config sections
    provider_name = config.get("provider")
    if not provider_name:
        found = [p for p in KNOWN_PROVIDERS if p in config]
        if len(found) == 0:
            fatal_error("No provider section found in config file. Expected one of: " + ", ".join(KNOWN_PROVIDERS))
        if len(found) > 1:
            fatal_error("Multiple provider sections found in config file. Please add a 'provider:' key to select one.")
        provider_name = found[0]

    if provider_name not in config:
        fatal_error(f"Provider '{provider_name}' specified but no '{provider_name}' section found in config file")

    provider_config = config[provider_name]
    return Config(
        provider_name=provider_name,
        provider_config=provider_config,
        ssh_keys=_get_ssh_keys(provider_config, provider_name),
        dns_zone=provider_config.get("dns-zone"),
        machine_sizes=_get_machine_sizes(provider_config, provider_name),
        image=_require_key(provider_config, "image", provider_name),
        regions=_get_regions(provider_config, provider_name),
        project=provider_config.get("project"),
    )


def get_machine(name: str) -> MachineConfig:
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    config = _loaded_config.c
    if "machines" not in config:
        fatal_error("Required 'machines' section not found in config file")
    config_machines = config["machines"]
    if name not in config_machines:
        fatal_error(f"Machine type '{name}' not found in config file. Available types: {', '.join(config_machines.keys())}")
    target_config = config_machines[name]
    script_args = target_config.get("script-args")
    if script_args is not None and not isinstance(script_args, (str, list)):
        fatal_error(f"Config key 'script-args' in 'machines.{name}' must be a string or a list of strings")
    if isinstance(script_args, list) and not all(isinstance(item, (str, int, float, bool)) for item in script_args):
        fatal_error(f"Config key 'script-args' in 'machines.{name}' must be a list of scalar values")
    return MachineConfig(
        _require_key(target_config, "new-user-name", f"machines.{name}"),
        target_config.get("script-url"),
        target_config.get("script-dir"),
        target_config.get("script-path"),
        script_args,
        _get_firewall(target_config, f"machines.{name}"),
    )


def has_machine(name: str) -> bool:
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    return name in (_loaded_config.c.get("machines") or {})


def get_machines():
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    config = _loaded_config.c

    if "machines" not in config:
        fatal_error("Required 'machines' section not found in config file")
    ret = {}
    for name in config["machines"]:
        ret[name] = get_machine(name)
    return ret
