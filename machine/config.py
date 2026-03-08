import os
import re
from pathlib import Path
from machine.di import d
from machine.factory import yaml
from machine.log import fatal_error, debug
from machine.types import Config, MachineConfig
from machine import constants

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


def _load_config_data(config_file_name: str):
    if not config_file_name:
        config_file_name = constants.default_config_file_path
    config_path = Path(os.path.expanduser(config_file_name))
    if not config_path.exists():
        fatal_error(f"Error: Config file: {config_path} not found")
    config = _expand_env_vars(yaml().load(open(config_path, "r")))
    if d.opt.debug:
        debug(f"Loaded config file: {config_path}")
        debug(f"Parsed config: {config}")
    _loaded_config.c = config
    return config


def get(config_file_name: str) -> Config:
    config = _load_config_data(config_file_name)
    config_do = config["digital-ocean"]
    return Config(
        config_do["access-token"],
        config_do["ssh-key"],
        config_do.get("dns-zone"),
        config_do["machine-size"],
        config_do["image"],
        config_do["region"],
        config_do["project"],
    )


def get_machine(name: str) -> MachineConfig:
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    config = _loaded_config.c
    config_machines = config["machines"]
    target_config = config_machines[name]
    return MachineConfig(
        target_config["new-user-name"],
        target_config.get("script-url"),
        target_config.get("script-dir"),
        target_config.get("script-path"),
        target_config.get("script-args"),
    )


def get_machines():
    if not _loaded_config.c:
        fatal_error("Attempt to fetch machine data before config loaded")
    config = _loaded_config.c

    ret = {}
    for name in config["machines"]:
        ret[name] = get_machine(name)
    return ret
