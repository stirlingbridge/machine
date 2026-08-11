"""Tests for Vultr instance deletion.

Vultr refuses to delete an instance that is still provisioning, and has been
observed to accept the DELETE without acting on it, which leaked one VM per e2e
run until the account instance limit was hit (issue #102).
"""

import json

import pytest
import requests

from vultr import VultrException

from machine.providers import vultr as vultr_module
from machine.providers.vultr import VultrProvider


def _exception(status, error="boom"):
    response = requests.Response()
    response.status_code = status
    response.headers["content-type"] = "application/json"
    response._content = json.dumps({"error": error}).encode()
    return VultrException(response)


class FakeClient:
    """Stands in for vultr.Vultr, scripting the API's replies."""

    def __init__(self, delete_results, get_results):
        self.delete_results = list(delete_results)
        self.get_results = list(get_results)
        self.delete_calls = 0
        self.get_calls = 0

    def delete_instance(self, instance_id):
        self.delete_calls += 1
        result = self.delete_results.pop(0) if self.delete_results else None
        if isinstance(result, Exception):
            raise result
        return result

    def get_instance(self, instance_id):
        self.get_calls += 1
        result = self.get_results.pop(0) if self.get_results else _exception(404, "not found")
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def provider(monkeypatch):
    """A provider whose clock only advances when the code sleeps.

    destroy_vm budgets itself in minutes of wall clock, so the tests drive a
    fake clock rather than waiting for it.
    """
    now = [0.0]
    monkeypatch.setattr(vultr_module, "Vultr", lambda api_key: None)
    monkeypatch.setattr(vultr_module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(vultr_module.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return VultrProvider({"api-key": "test-key"})


def test_destroy_succeeds_when_instance_disappears(provider):
    """The happy path: the delete is accepted and the instance goes away."""
    provider._client = FakeClient(delete_results=[None], get_results=[_exception(404)])
    assert provider.destroy_vm("abc") is True
    assert provider._client.delete_calls == 1


def test_destroy_retries_when_delete_is_accepted_but_ignored(provider):
    """The leak from issue #102: DELETE returns 204 but the instance survives."""
    provider._client = FakeClient(
        delete_results=[None, None],
        # First confirmation: still there for the whole confirm window, then gone.
        get_results=[{"id": "abc"}] * 20 + [_exception(404)],
    )
    assert provider.destroy_vm("abc") is True
    assert provider._client.delete_calls == 2


@pytest.mark.parametrize("status", [400, 500])
def test_destroy_retries_while_instance_is_locked(provider, status):
    """Vultr has signalled 'still provisioning' with more than one status code."""
    provider._client = FakeClient(
        delete_results=[_exception(status, "instance is currently locked"), None],
        get_results=[_exception(404)],
    )
    assert provider.destroy_vm("abc") is True
    assert provider._client.delete_calls == 2


def test_destroy_treats_missing_instance_as_success(provider):
    provider._client = FakeClient(delete_results=[_exception(404, "not found")], get_results=[])
    assert provider.destroy_vm("abc") is True


def test_destroy_gives_up_immediately_on_auth_failure(provider):
    """Retrying a rejected API key would only stall for the full timeout."""
    provider._client = FakeClient(delete_results=[_exception(401, "invalid key")] * 10, get_results=[])
    with pytest.raises(SystemExit):
        provider.destroy_vm("abc")
    assert provider._client.delete_calls == 1


def test_destroy_fails_when_instance_never_goes_away(provider):
    provider._client = FakeClient(delete_results=[None] * 500, get_results=[{"id": "abc"}] * 500)
    with pytest.raises(SystemExit):
        provider.destroy_vm("abc")
