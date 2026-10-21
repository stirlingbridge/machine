import re

import digitalocean
from digitalocean.baseapi import POST, PUT

from machine.log import fatal_error, info
from machine.provider import CloudProvider, CapacityUnavailableError, VM, SSHKey, DNSRecord
from machine.types import FirewallConfig


# fmt: off
VALID_REGIONS = [
    "NYC1", "NYC3", "AMS3", "SFO2", "SFO3", "SGP1", "LON1", "FRA1",
    "TOR1", "BLR1", "SYD1", "ATL1", "RIC1", "MKC1", "MEM1",
]
# fmt: on

VALID_IMAGES = [
    "almalinux-8-x64",
    "almalinux-9-x64",
    "centos-stream-9-x64",
    "debian-11-x64",
    "debian-12-x64",
    "fedora-39-x64",
    "fedora-40-x64",
    "rockylinux-9-x64",
    "rockylinux-8-x64",
    "ubuntu-20-04-x64",
    "ubuntu-22-04-x64",
    "ubuntu-24-04-x64",
]


# A DigitalOcean firewall with no outbound rules blocks all outbound traffic, so
# "outbound not specified" has to be spelled out as allow-all.
_ALL_ADDRESSES = ["0.0.0.0/0", "::/0"]
_ALLOW_ALL_OUTBOUND = [
    {"protocol": "tcp", "ports": "all", "destinations": {"addresses": _ALL_ADDRESSES}},
    {"protocol": "udp", "ports": "all", "destinations": {"addresses": _ALL_ADDRESSES}},
    {"protocol": "icmp", "destinations": {"addresses": _ALL_ADDRESSES}},
]


def _firewall_name(name) -> str:
    # Firewall names must start with an alphanumeric and contain only alphanumerics, '.' and '-'
    return re.sub(r"[^A-Za-z0-9.-]", "-", name).lstrip(".-")


def _firewall_rules(rules, address_key) -> list:
    ret = []
    for rule in rules:
        do_rule = {"protocol": rule.protocol, address_key: {"addresses": rule.addresses}}
        if rule.protocol != "icmp":
            do_rule["ports"] = rule.ports
        ret.append(do_rule)
    return ret


# What DigitalOcean says when it is out of capacity for a size in a region.
CAPACITY_ERROR_MARKERS = ["Size is not available in this region"]


def _droplet_to_vm(droplet) -> VM:
    region = droplet.region
    if isinstance(region, dict):
        region = region.get("slug")
    return VM(
        id=str(droplet.id),
        name=droplet.name,
        tags=droplet.tags,
        region=region,
        ip_address=droplet.ip_address,
        status=droplet.status,
        size=droplet.size_slug,
    )


class DigitalOceanProvider(CloudProvider):
    def __init__(self, provider_config):
        if "access-token" not in provider_config:
            fatal_error("Required key 'access-token' not found in 'digital-ocean' section of config file")
        self.token = provider_config["access-token"]
        self._manager = digitalocean.Manager(token=self.token)
        # The size list, fetched once for checking several regions and sizes.
        self._sizes = None

    def create_vm(self, name, region, image, size, ssh_key_names, tags, user_data) -> VM:
        ssh_keys = []
        for ssh_key_name in ssh_key_names:
            ssh_key = self._get_do_ssh_key(ssh_key_name)
            if not ssh_key:
                fatal_error(f"Error: SSH key '{ssh_key_name}' not found in DigitalOcean")
            ssh_keys.append(ssh_key)

        droplet = digitalocean.Droplet(
            token=self.token,
            name=name,
            region=region,
            image=image,
            size_slug=size,
            ssh_keys=ssh_keys,
            tags=tags,
            user_data=user_data,
            backups=False,
        )
        try:
            droplet.create()
        except digitalocean.DataReadError as e:
            # The wording of a stockout error isn't documented, so also ask
            # (afresh) whether the size is still offered in the region.
            self._sizes = None
            if any(m.lower() in str(e).lower() for m in CAPACITY_ERROR_MARKERS) or self.has_capacity(region, size) is False:
                raise CapacityUnavailableError(f"DigitalOcean has no capacity for size {size} in region {region}: {e}")
            fatal_error(f"DigitalOcean API error creating VM: {e}")
        return _droplet_to_vm(droplet)

    def get_vm(self, vm_id) -> VM:
        droplet = self._manager.get_droplet(vm_id)
        return _droplet_to_vm(droplet)

    def destroy_vm(self, vm_id) -> bool:
        try:
            droplet = self._manager.get_droplet(vm_id)
        except digitalocean.NotFoundError:
            fatal_error(f"Error: machine with id {vm_id} not found")
        result = droplet.destroy()
        return result

    def list_vms(self, tag=None) -> list:
        if tag:
            droplets = self._manager.get_all_droplets(tag_name=tag)
        else:
            droplets = self._manager.get_all_droplets()
        return [_droplet_to_vm(d) for d in droplets]

    def get_ssh_key(self, name) -> SSHKey:
        do_key = self._get_do_ssh_key(name)
        if not do_key:
            return None
        return SSHKey(
            id=str(do_key.id),
            name=do_key.name,
            fingerprint=do_key.fingerprint,
            public_key=do_key.public_key,
        )

    def list_ssh_keys(self) -> list:
        keys = self._manager.get_all_sshkeys()
        return [SSHKey(id=str(k.id), name=k.name, fingerprint=k.fingerprint, public_key=k.public_key) for k in keys]

    def create_dns_record(self, zone, record_type, name, data, ttl, tag=None) -> str:
        domain = digitalocean.Domain(token=self.token, name=zone)
        try:
            record = domain.create_new_domain_record(type=record_type, ttl=ttl, name=name, data=data, tag=tag)
        except digitalocean.NotFoundError:
            info(f"Warning: DNS zone '{zone}' not found in DigitalOcean, DNS record not set")
            return None
        return record

    def delete_dns_record(self, zone, record_name) -> bool:
        domain = digitalocean.Domain(token=self.token, name=zone)
        records = domain.get_records()
        for record in records:
            if record.name == record_name:
                domain.delete_domain_record(id=record.id)
                return True
        return False

    def get_dns_records(self, zone) -> list:
        domain = digitalocean.Domain(token=self.token, name=zone)
        records = domain.get_records()
        return [DNSRecord(id=str(r.id), name=r.name, type=r.type, data=r.data, ttl=r.ttl) for r in records]

    def list_domains(self) -> list:
        domains = self._manager.get_all_domains()
        return [d.name for d in domains]

    def list_projects(self) -> list:
        projects = self._manager.get_all_projects()
        return [p.name for p in projects]

    def assign_to_project(self, project_name, vm_id):
        projects = self._manager.get_all_projects()
        project = None
        for p in projects:
            if p.name == project_name:
                project = p
                break
        if not project:
            fatal_error(f"Error: Project {project_name} does not exist, machine created but not assigned to project")
        project.assign_resource([f"do:droplet:{vm_id}"])

    def apply_firewall(self, name, tag, firewall: FirewallConfig):
        name = _firewall_name(name)
        # The firewall can only reference a tag that already exists
        try:
            digitalocean.Tag(token=self.token, name=tag).create()
        except digitalocean.DataReadError as e:
            fatal_error(f"DigitalOcean API error creating tag {tag}: {e}")
        params = {
            "name": name,
            "tags": [tag],
            "inbound_rules": _firewall_rules(firewall.inbound, "sources"),
            "outbound_rules": (
                _ALLOW_ALL_OUTBOUND if firewall.outbound is None else _firewall_rules(firewall.outbound, "destinations")
            ),
        }
        existing = next((f for f in self._manager.get_all_firewalls() if f.name == name), None)
        try:
            if existing:
                # PUT replaces the whole firewall, so carry over anything else it's attached to
                params["tags"] = sorted(set((existing.tags or []) + [tag]))
                params["droplet_ids"] = existing.droplet_ids or []
                self._manager.get_data(f"firewalls/{existing.id}", type=PUT, params=params)
            else:
                self._manager.get_data("firewalls", type=POST, params=params)
        except digitalocean.DataReadError as e:
            fatal_error(f"DigitalOcean API error applying firewall {name}: {e}")
        return name

    def validate_region(self, region):
        if region is not None and region.upper() not in VALID_REGIONS:
            fatal_error(f"Error: region {region} is not one of {VALID_REGIONS}")

    def has_capacity(self, region, size):
        # A size's regions are the ones it can be created in right now: those
        # out of stock are dropped from the list.
        if self._sizes is None:
            try:
                self._sizes = self._manager.get_all_sizes()
            except digitalocean.Error:
                return None
        for s in self._sizes:
            if s.slug == size:
                return bool(getattr(s, "available", True)) and region.lower() in [r.lower() for r in s.regions]
        return None

    def validate_image(self, image):
        if image is not None and image not in VALID_IMAGES:
            info(f"Warning: image {image} is not one of these known valid images: {VALID_IMAGES}")

    def _get_do_ssh_key(self, name):
        keys = self._manager.get_all_sshkeys()
        for key in keys:
            if key.name == name:
                return key
        return None

    @property
    def provider_name(self) -> str:
        return "DigitalOcean"
