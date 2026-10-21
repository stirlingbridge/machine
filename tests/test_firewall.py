"""Tests for machine-type firewall config parsing and the DigitalOcean
firewall implementation."""

from unittest.mock import patch

import pytest
from digitalocean.baseapi import GET, POST, PUT

from machine.config import _get_firewall
from machine.factory import yaml
from machine.providers.digitalocean import DigitalOceanProvider, _firewall_name
from machine.types import FirewallConfig, FirewallRule


def _parse(text):
    return _get_firewall(yaml().load(text), "machines.test")


class TestGetFirewall:
    def test_no_firewall_section(self):
        assert _get_firewall({}, "machines.test") is None

    def test_inbound_rules_parsed(self):
        firewall = _parse(
            """
firewall:
  inbound:
    - protocol: tcp
      ports: 2222
      sources: [203.0.113.10/32, "2001:db8::/32"]
    - protocol: icmp
      sources: 0.0.0.0/0
"""
        )
        assert firewall.inbound == [
            FirewallRule(protocol="tcp", ports="2222", addresses=["203.0.113.10/32", "2001:db8::/32"]),
            FirewallRule(protocol="icmp", ports=None, addresses=["0.0.0.0/0"]),
        ]

    def test_outbound_omitted_means_allow_all(self):
        firewall = _parse("firewall:\n  inbound: []\n")
        assert firewall.outbound is None

    def test_outbound_empty_means_block_all(self):
        firewall = _parse("firewall:\n  outbound: []\n")
        assert firewall.outbound == []

    def test_outbound_rules_parsed(self):
        firewall = _parse(
            """
firewall:
  outbound:
    - protocol: udp
      ports: "53"
      destinations: [1.1.1.1]
"""
        )
        assert firewall.outbound == [FirewallRule(protocol="udp", ports="53", addresses=["1.1.1.1"])]

    def test_tcp_ports_default_to_all(self):
        firewall = _parse("firewall:\n  inbound:\n    - protocol: tcp\n      sources: [10.0.0.0/8]\n")
        assert firewall.inbound[0].ports == "all"

    def test_port_range_accepted(self):
        firewall = _parse("firewall:\n  inbound:\n    - protocol: tcp\n      ports: 8000-9000\n      sources: [10.0.0.0/8]\n")
        assert firewall.inbound[0].ports == "8000-9000"

    @pytest.mark.parametrize(
        "rule",
        [
            "{protocol: gre, sources: [10.0.0.0/8]}",
            "{protocol: tcp, ports: ssh, sources: [10.0.0.0/8]}",
            "{protocol: icmp, ports: 1, sources: [10.0.0.0/8]}",
            "{protocol: tcp, ports: 22}",
            "{protocol: tcp, ports: 22, sources: []}",
            "{protocol: tcp, ports: 22, sources: [203.0.113.300/32]}",
            "{ports: 22, sources: [10.0.0.0/8]}",
        ],
    )
    def test_invalid_rules_are_fatal(self, rule):
        with pytest.raises(SystemExit):
            _parse(f"firewall:\n  inbound:\n    - {rule}\n")

    def test_destinations_required_for_outbound(self):
        with pytest.raises(SystemExit):
            _parse("firewall:\n  outbound:\n    - {protocol: tcp, ports: 443, sources: [0.0.0.0/0]}\n")


class TestFirewallName:
    def test_invalid_characters_replaced(self):
        assert _firewall_name("machine-acme_host") == "machine-acme-host"

    def test_leading_punctuation_stripped(self):
        assert _firewall_name("_acme") == "acme"


def _provider(existing_firewalls=()):
    with patch("machine.providers.digitalocean.digitalocean.Manager") as manager_class:
        provider = DigitalOceanProvider({"access-token": "token"})
    manager = manager_class.return_value

    def get_data(url, type=GET, params=None):
        return {"firewalls": list(existing_firewalls)} if (url, type) == ("firewalls", GET) else {}

    manager.get_data.side_effect = get_data
    return provider, manager


_FIREWALL = FirewallConfig(
    inbound=[FirewallRule(protocol="tcp", ports="2222", addresses=["203.0.113.10/32"])],
    outbound=[
        FirewallRule(protocol="tcp", ports="443", addresses=["0.0.0.0/0"]),
        FirewallRule(protocol="icmp", ports=None, addresses=["0.0.0.0/0"]),
    ],
)


class TestDigitalOceanApplyFirewall:
    @patch("machine.providers.digitalocean.digitalocean.Tag")
    def test_creates_new_firewall_for_tag(self, tag_class):
        provider, manager = _provider()
        name = provider.apply_firewall("machine-acme", "machine:type:acme", _FIREWALL)

        assert name == "machine-acme"
        tag_class.assert_called_once_with(token="token", name="machine:type:acme")
        tag_class.return_value.create.assert_called_once()
        manager.get_data.assert_called_with(
            "firewalls",
            type=POST,
            params={
                "name": "machine-acme",
                "tags": ["machine:type:acme"],
                "inbound_rules": [{"protocol": "tcp", "ports": "2222", "sources": {"addresses": ["203.0.113.10/32"]}}],
                "outbound_rules": [
                    {"protocol": "tcp", "ports": "443", "destinations": {"addresses": ["0.0.0.0/0"]}},
                    {"protocol": "icmp", "destinations": {"addresses": ["0.0.0.0/0"]}},
                ],
            },
        )

    @patch("machine.providers.digitalocean.digitalocean.Tag")
    def test_updates_existing_firewall_preserving_attachments(self, tag_class):
        # As the API returns it, including the rule fields python-digitalocean's own
        # Firewall objects reject
        existing = {
            "id": "fw-1",
            "name": "machine-acme",
            "tags": ["other-tag"],
            "droplet_ids": [42],
            "inbound_rules": [{"protocol": "tcp", "ports": "22", "sources": {"addresses": ["0.0.0.0/0"]}, "action": "allow"}],
        }
        provider, manager = _provider([existing])
        provider.apply_firewall("machine-acme", "machine:type:acme", _FIREWALL)

        args, kwargs = manager.get_data.call_args
        assert args == ("firewalls/fw-1",)
        assert kwargs["type"] == PUT
        assert kwargs["params"]["tags"] == ["machine:type:acme", "other-tag"]
        assert kwargs["params"]["droplet_ids"] == [42]

    @patch("machine.providers.digitalocean.digitalocean.Tag")
    def test_unspecified_outbound_allows_all(self, tag_class):
        provider, manager = _provider()
        provider.apply_firewall("machine-acme", "machine:type:acme", FirewallConfig(inbound=[], outbound=None))

        outbound = manager.get_data.call_args.kwargs["params"]["outbound_rules"]
        assert {r["protocol"] for r in outbound} == {"tcp", "udp", "icmp"}
        assert all(r["destinations"]["addresses"] == ["0.0.0.0/0", "::/0"] for r in outbound)
