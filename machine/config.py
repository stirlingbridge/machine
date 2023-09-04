

import os
from pathlib import Path
from machine.di import d
from machine.factory import yaml
from machine.log import fatal_error, debug
from machine.types import Config, MachineConfig
from machine import constants


def _load_config_data():
    config_path = Path(os.path.expanduser(constants.config_file_path))
    if not config_path.exists():
        fatal_error(f"Error: Config file: {config_path} not found")
    config = yaml().load(open(config_path, "r"))
    if d.opt.debug:
        debug(f"Parsed config: {config}")
    return config


def get() -> Config:
    config = _load_config_data()
    config_do = config["digital-ocean"]
    return Config(config_do["access-token"], config_do["ssh-key"], config_do["dns-zone"], config_do["machine-size"],
                  config_do["image"], config_do["region"], config_do["project"])


def get_machine(name: str) -> MachineConfig:
    config = _load_config_data()
    config_machines = config["machines"]
    target_config = config_machines[name]
    return MachineConfig(
        target_config["new-user-name"],
        target_config["script-url"],
        target_config["script-dir"],        
        target_config["script-path"],
        target_config["script-args"],
    )
