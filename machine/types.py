from dataclasses import dataclass

TAG_MACHINE_CREATED = "machine:created"
TAG_MACHINE_TYPE_PREFIX = "machine:type:"
TAG_MACHINE_SESSION_PREFIX = "machine:session:"


@dataclass
class CliOptions:
    debug: bool
    quiet: bool
    verbose: bool
    dry_run: bool


@dataclass
class Config:
    provider_name: str
    provider_config: dict
    ssh_keys: list
    dns_zone: str
    machine_sizes: list
    image: str
    regions: list
    project: str


@dataclass
class MainCmdCtx:
    config: Config
    session_id: str
    provider: object  # CloudProvider instance


@dataclass
class FirewallRule:
    protocol: str
    ports: str
    addresses: list


@dataclass
class FirewallConfig:
    inbound: list
    # None means outbound rules were not specified: all outbound traffic is allowed
    outbound: list


@dataclass
class MachineConfig:
    new_user_name: str
    script_url: str
    script_dir: str
    script_path: str
    script_args: "str | list"
    firewall: FirewallConfig = None
