from dataclasses import dataclass


@dataclass
class CliOptions:
    debug: bool
    quiet: bool
    verbose: bool
    dry_run: bool


@dataclass
class Config:
    access_token: str
    ssh_key: str
    dns_zone: str
    machine_size: str
    image: str
    region: str
    project: str


@dataclass
class MainCmdCtx:
    config: Config


@dataclass
class MachineConfig:
    new_user_name: str
    script_url: str
    script_dir: str
    script_path: str
    script_args: str
