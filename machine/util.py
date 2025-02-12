import os
import uuid

from digitalocean import Domain, Manager, Project, SSHKey

from machine.factory import yaml
from machine.constants import default_config_dir_path, default_session_id_file_path
from machine.types import TAG_MACHINE_TYPE_PREFIX, TAG_MACHINE_CREATED

from machine.types import MainCmdCtx, TAG_MACHINE_SESSION_PREFIX


def projectFromName(manager: Manager, name: str) -> Project:
    projects = manager.get_all_projects()
    for project in projects:
        if project.name == name:
            return project
    return None


def sshKeyFromName(manager: Manager, name: str) -> SSHKey:
    keys = manager.get_all_sshkeys()
    for key in keys:
        if key.name == name:
            return key
    return None


def dnsRecordIdFromName(domain: Domain, name: str) -> str:
    records = domain.get_records()
    for record in records:
        if record.name == name:
            return record.id
    return None


def get_machine_type(droplet):
    type = next((t for t in droplet.tags if TAG_MACHINE_TYPE_PREFIX in t), "").replace(TAG_MACHINE_TYPE_PREFIX, "")
    if not type:
        return None
    return type


def is_machine_created(droplet):
    return TAG_MACHINE_CREATED in droplet.tags


def is_same_session(command_context: MainCmdCtx, droplet):
    return TAG_MACHINE_SESSION_PREFIX + command_context.session_id in droplet.tags


def load_session_id():
    if not os.path.exists(default_config_dir_path):
        os.mkdir(default_config_dir_path)

    if not os.path.exists(default_session_id_file_path):
        with open(default_session_id_file_path, "w") as f:
            f.write("id: " + str(uuid.uuid4()).replace("-", "")[0:8])

    sessionid_config = yaml().load(open(default_session_id_file_path, "r"))
    return sessionid_config["id"]


def json_droplet(droplet):
    return {
        "id": droplet.id,
        "name": droplet.name,
        "tags": droplet.tags,
        "region": droplet.region["slug"],
        "ip": droplet.ip_address,
        "type": get_machine_type(droplet),
    }


def json_dns_record(dns_record, zone, droplet):
    if droplet:
        droplet = json_droplet(droplet)

    return {
        "id": dns_record.id,
        "droplet": droplet,
        "name": dns_record.name,
        "fqdn": f"{dns_record.name}.{zone}",
        "zone": zone,
        "data": dns_record.data,
        "ttl": dns_record.ttl,
        "type": dns_record.type,
    }
