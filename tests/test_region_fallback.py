"""Tests for creating a machine in the first of several regions, and with the
first of several sizes, that has capacity, for when a provider is out of stock
of a size in a region."""

import json

import digitalocean
import pytest
import requests

from vultr import VultrException

from machine import di
from machine.provider import CapacityUnavailableError, VM
from machine.providers.digitalocean import DigitalOceanProvider
from machine.providers.vultr import VultrProvider
from machine.subcommands import create
from machine.types import CliOptions


@pytest.fixture(autouse=True)
def options():
    saved = di.d.opt
    di.d.opt = CliOptions(debug=False, quiet=False, verbose=False, dry_run=False)
    yield
    di.d.opt = saved


class FakeProvider:
    """Out of capacity in the regions (or (region, size) pairs) in `full`;
    `reported_full` is what has_capacity says, which may be out of date."""

    def __init__(self, full=(), reported_full=()):
        self.full = set(full)
        self.reported_full = set(reported_full)
        self.attempts = []

    def has_capacity(self, region, size):
        return region not in self.reported_full and (region, size) not in self.reported_full

    def create_vm(self, name, region, size, **kwargs):
        self.attempts.append(region if self.single_size else (region, size))
        if region in self.full or (region, size) in self.full:
            raise CapacityUnavailableError(f"no capacity for {size} in {region}")
        return VM(id="1", name=name, tags=[], region=region, ip_address="", status="new", size=size)


def _create(provider, regions, sizes=("s-1",)):
    provider.single_size = len(sizes) == 1
    return create._create_with_first_available(provider, regions, list(sizes), name="m", image="img")


class TestCreateWithFirstAvailable:
    def test_single_region_with_capacity(self):
        provider = FakeProvider()
        assert _create(provider, ["nyc3"]).region == "nyc3"
        assert provider.attempts == ["nyc3"]

    def test_falls_back_to_next_region(self, capsys):
        provider = FakeProvider(full={"nyc3"})
        assert _create(provider, ["nyc3", "nyc1", "tor1"]).region == "nyc1"
        assert provider.attempts == ["nyc3", "nyc1"]
        assert "Region: nyc1" in capsys.readouterr().err

    def test_regions_reported_full_are_tried_last(self):
        provider = FakeProvider(reported_full={"nyc3"})
        assert _create(provider, ["nyc3", "nyc1"]).region == "nyc1"
        assert provider.attempts == ["nyc1"]

    def test_region_reported_full_is_still_tried(self):
        provider = FakeProvider(full={"nyc1"}, reported_full={"nyc3"})
        assert _create(provider, ["nyc3", "nyc1"]).region == "nyc3"
        assert provider.attempts == ["nyc1", "nyc3"]

    def test_all_regions_full_exits(self, capsys):
        provider = FakeProvider(full={"nyc3", "nyc1"})
        with pytest.raises(SystemExit):
            _create(provider, ["nyc3", "nyc1"])
        assert provider.attempts == ["nyc3", "nyc1"]
        assert "no capacity for size s-1 in any region tried: nyc3, nyc1" in capsys.readouterr().err

    def test_falls_back_to_next_size_in_the_same_region(self, capsys):
        provider = FakeProvider(full={("nyc3", "s-1")})
        vm = _create(provider, ["nyc3", "nyc1"], ["s-1", "s-1-intel"])
        assert (vm.region, vm.size) == ("nyc3", "s-1-intel")
        assert provider.attempts == [("nyc3", "s-1"), ("nyc3", "s-1-intel")]
        assert "Size: s-1-intel" in capsys.readouterr().err

    def test_every_size_is_tried_before_the_next_region(self):
        provider = FakeProvider(full={"nyc3"})
        vm = _create(provider, ["nyc3", "nyc1"], ["s-1", "s-1-intel"])
        assert (vm.region, vm.size) == ("nyc1", "s-1")
        assert provider.attempts == [("nyc3", "s-1"), ("nyc3", "s-1-intel"), ("nyc1", "s-1")]

    def test_sizes_reported_full_are_tried_last(self):
        provider = FakeProvider(reported_full={("nyc3", "s-1")})
        vm = _create(provider, ["nyc3"], ["s-1", "s-1-intel"])
        assert (vm.region, vm.size) == ("nyc3", "s-1-intel")
        assert provider.attempts == [("nyc3", "s-1-intel")]

    def test_no_capacity_for_any_size_lists_them(self, capsys):
        provider = FakeProvider(full={"nyc3"})
        with pytest.raises(SystemExit):
            _create(provider, ["nyc3"], ["s-1", "s-1-intel"])
        assert "no capacity for size s-1, s-1-intel in any region tried: nyc3" in capsys.readouterr().err

    def test_other_errors_are_not_retried(self):
        class FailingProvider(FakeProvider):
            def create_vm(self, name, region, size, **kwargs):
                self.attempts.append(region)
                raise SystemExit(1)

        provider = FailingProvider()
        with pytest.raises(SystemExit):
            _create(provider, ["nyc3", "nyc1"])
        assert provider.attempts == ["nyc3"]


class FakeSize:
    def __init__(self, slug, regions, available=True):
        self.slug = slug
        self.regions = regions
        self.available = available


class TestDigitalOceanCapacity:
    @pytest.fixture()
    def provider(self, monkeypatch):
        provider = DigitalOceanProvider({"access-token": "fake"})
        monkeypatch.setattr(provider, "_get_do_ssh_key", lambda name: object())
        monkeypatch.setattr(provider._manager, "get_all_sizes", lambda: [FakeSize("s-1", ["nyc1"])])
        return provider

    def _fail_create(self, monkeypatch, message):
        def create(self):
            raise digitalocean.DataReadError(message)

        monkeypatch.setattr(digitalocean.Droplet, "create", create)

    def _create(self, provider, region):
        return provider.create_vm("m", region, "img", "s-1", ["key"], [], None)

    def test_has_capacity(self, provider):
        assert provider.has_capacity("nyc1", "s-1") is True
        assert provider.has_capacity("NYC3", "s-1") is False
        assert provider.has_capacity("nyc1", "unknown-size") is None

    def test_stockout_message_is_capacity_error(self, provider, monkeypatch):
        monkeypatch.setattr(provider, "has_capacity", lambda region, size: None)
        self._fail_create(monkeypatch, "Size is not available in this region.")
        with pytest.raises(CapacityUnavailableError):
            self._create(provider, "nyc1")

    def test_size_not_offered_is_capacity_error(self, provider, monkeypatch):
        self._fail_create(monkeypatch, "some new wording")
        with pytest.raises(CapacityUnavailableError):
            self._create(provider, "nyc3")

    def test_other_error_is_fatal(self, provider, monkeypatch):
        self._fail_create(monkeypatch, "Image not found")
        with pytest.raises(SystemExit):
            self._create(provider, "nyc1")


class FakeVultrClient:
    def __init__(self, available_plans):
        self.available_plans = available_plans

    def get(self, url, params=None):
        return {"available_plans": self.available_plans}

    def list_keys(self):
        return [{"id": "k1", "name": "key"}]

    def create_instance(self, region, plan, **kwargs):
        response = requests.Response()
        response.status_code = 400
        response.headers["content-type"] = "application/json"
        response._content = json.dumps({"error": "boom"}).encode()
        raise VultrException(response)


class TestVultrCapacity:
    def _provider(self, available_plans):
        provider = VultrProvider({"api-key": "fake"})
        provider._client = FakeVultrClient(available_plans)
        return provider

    def test_has_capacity(self):
        provider = self._provider(["vc2-1c-1gb"])
        assert provider.has_capacity("ewr", "vc2-1c-1gb") is True
        assert provider.has_capacity("ewr", "vc2-2c-4gb") is False

    def test_plan_not_offered_is_capacity_error(self):
        with pytest.raises(CapacityUnavailableError):
            self._provider([]).create_vm("m", "ewr", "2136", "vc2-1c-1gb", ["key"], [], None)

    def test_other_error_is_fatal(self):
        with pytest.raises(SystemExit):
            self._provider(["vc2-1c-1gb"]).create_vm("m", "ewr", "2136", "vc2-1c-1gb", ["key"], [], None)
