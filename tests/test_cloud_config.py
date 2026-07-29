"""Tests for cloud-init user-data generation, including provisioning of
one or more SSH keys onto the new user."""

import pytest

from machine.cloud_config import get_user_data
from machine.factory import yaml
from machine.provider import SSHKey
from machine.types import MachineConfig


class FakeProvider:
    """Minimal CloudProvider stand-in that resolves a fixed set of keys."""

    provider_name = "Fake"
    _keys = {
        "alice": "ssh-rsa AAAAalice alice@host",
        "bob": "ssh-ed25519 AAAAbob bob@host",
    }

    def get_ssh_key(self, name):
        public_key = self._keys.get(name)
        if public_key is None:
            return None
        return SSHKey(id=name, name=name, fingerprint="", public_key=public_key)


def _machine_config(script_args=None):
    if script_args is None:
        return MachineConfig("admin", None, None, None, None)
    return MachineConfig(
        "admin",
        "https://example.com/scripts/combine.sh",
        "/opt/admin",
        "/opt/admin/combine.sh",
        script_args,
    )


def _authorized_keys(user_data):
    """Parse generated user-data and return the new user's authorized keys."""
    parsed = yaml().load(user_data)
    return list(parsed["users"][0]["ssh-authorized-keys"])


class TestGetUserData:
    def test_single_key_installed(self):
        """The original single-name form installs exactly that key."""
        user_data = get_user_data(FakeProvider(), ["alice"], "", _machine_config())
        assert _authorized_keys(user_data) == ["ssh-rsa AAAAalice alice@host"]

    def test_multiple_keys_installed(self):
        """A list of names installs every resolved key, in order."""
        user_data = get_user_data(FakeProvider(), ["alice", "bob"], "host.example.com", _machine_config())
        assert _authorized_keys(user_data) == [
            "ssh-rsa AAAAalice alice@host",
            "ssh-ed25519 AAAAbob bob@host",
        ]

    def test_generated_user_data_is_valid_yaml(self):
        """Generated user-data must parse as YAML so cloud-init can consume it."""
        user_data = get_user_data(FakeProvider(), ["alice", "bob"], "", _machine_config())
        assert user_data.startswith("#cloud-config")
        parsed = yaml().load(user_data)
        assert parsed["users"][0]["name"] == "admin"

    def test_unknown_key_is_fatal(self):
        """A key name the provider cannot resolve aborts with a clear error."""
        with pytest.raises(SystemExit):
            get_user_data(FakeProvider(), ["alice", "ghost"], "", _machine_config())


def _run_command(user_data):
    """Parse generated user-data and return the shell command string passed to su -c."""
    parsed = yaml().load(user_data)
    su_cmd = parsed["runcmd"][-1]
    assert su_cmd[0] == "su"
    return su_cmd[2]


class TestScriptArgs:
    def test_string_args_passed_verbatim(self):
        """The legacy string form is interpolated into the command unchanged."""
        user_data = get_user_data(FakeProvider(), ["alice"], "", _machine_config("-y --flag value"))
        assert _run_command(user_data).endswith("/opt/admin/combine.sh -y --flag value")

    def test_list_args_quoted_one_argument_per_item(self):
        """Each list item becomes exactly one shell argument, spaces and all."""
        user_data = get_user_data(
            FakeProvider(),
            ["alice"],
            "",
            _machine_config(["packages.sh build-essential jq", "podman.sh"]),
        )
        assert _run_command(user_data).endswith(
            "/opt/admin/combine.sh 'packages.sh build-essential jq' podman.sh"
        )

    def test_list_args_expand_variables(self):
        """$MACHINE_* variables expand inside list items, like in the string form."""
        user_data = get_user_data(
            FakeProvider(), ["alice"], "host.example.com", _machine_config(["fqdn.sh $MACHINE_FQDN"])
        )
        assert _run_command(user_data).endswith("/opt/admin/combine.sh 'fqdn.sh host.example.com'")

    def test_list_args_user_data_is_valid_yaml(self):
        """List-form args must survive the YAML round trip cloud-init performs."""
        user_data = get_user_data(
            FakeProvider(), ["alice"], "", _machine_config(["k3s-node.sh -y --msg 'a b'"])
        )
        cmd = _run_command(user_data)
        assert "k3s-node.sh -y --msg" in cmd
