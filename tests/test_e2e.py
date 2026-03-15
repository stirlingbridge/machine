"""End-to-end tests that create real VMs on DigitalOcean.

These tests require a real DigitalOcean environment and are NOT run as part of
the normal test suite. They must be invoked explicitly:

    uv run pytest tests/test_e2e.py -v

Required environment variables:
    E2E_DO_TOKEN    - DigitalOcean API token
    E2E_SSH_KEY     - Name of an SSH key already registered in DO
    E2E_DNS_ZONE    - DNS zone managed by DO (e.g. "test.example.com")
    E2E_PROJECT     - DO project name to assign droplets to

Optional environment variables:
    E2E_REGION      - Region slug (default: nyc1)
    E2E_IMAGE       - Image slug (default: ubuntu-24-04-x64)
    E2E_SIZE        - Machine size slug (default: s-1vcpu-512mb-10gb)
"""

import json
import os
import subprocess
import uuid

import pytest


# ---------------------------------------------------------------------------
# Skip the entire module if credentials are not provided
# ---------------------------------------------------------------------------

E2E_DO_TOKEN = os.environ.get("E2E_DO_TOKEN")
E2E_SSH_KEY = os.environ.get("E2E_SSH_KEY")
E2E_DNS_ZONE = os.environ.get("E2E_DNS_ZONE")
E2E_REGION = os.environ.get("E2E_REGION", "nyc1")
E2E_IMAGE = os.environ.get("E2E_IMAGE", "ubuntu-24-04-x64")
E2E_SIZE = os.environ.get("E2E_SIZE", "s-1vcpu-512mb-10gb")
E2E_PROJECT = os.environ.get("E2E_PROJECT")

pytestmark = pytest.mark.e2e

_MISSING = []
if not E2E_DO_TOKEN:
    _MISSING.append("E2E_DO_TOKEN")
if not E2E_SSH_KEY:
    _MISSING.append("E2E_SSH_KEY")
if not E2E_DNS_ZONE:
    _MISSING.append("E2E_DNS_ZONE")
if not E2E_PROJECT:
    _MISSING.append("E2E_PROJECT")

if _MISSING:
    pytestmark = [
        pytest.mark.e2e,
        pytest.mark.skip(reason=f"E2E env vars not set: {', '.join(_MISSING)}"),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_name(prefix="e2etest"):
    """Generate a short unique droplet name safe for DNS."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _write_config(path, **overrides):
    """Write a minimal config file for the e2e test run."""
    cfg = {
        "access-token": E2E_DO_TOKEN,
        "ssh-key": E2E_SSH_KEY,
        "dns-zone": E2E_DNS_ZONE,
        "machine-size": E2E_SIZE,
        "image": E2E_IMAGE,
        "region": E2E_REGION,
    }
    cfg["project"] = E2E_PROJECT
    cfg.update(overrides)

    do_lines = "\n".join(f"  {k}: {v}" for k, v in cfg.items())
    content = f"digital-ocean:\n{do_lines}\nmachines:\n  e2e-basic:\n    new-user-name: e2euser\n"
    with open(path, "w") as f:
        f.write(content)


def run_machine(*args, config_file=None, session_id=None):
    """Run the machine CLI as a subprocess with the given arguments."""
    cmd = ["uv", "run", "machine"]
    if config_file:
        cmd += ["--config-file", str(config_file)]
    if session_id:
        cmd += ["--session-id", session_id]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result


def _extract_droplet_id(output_text):
    """Extract the droplet ID from CLI output like 'New droplet created with id: 12345'."""
    for line in output_text.splitlines():
        if "id:" in line.lower():
            parts = line.split("id:")
            if len(parts) >= 2:
                candidate = parts[-1].strip()
                if candidate.isdigit():
                    return candidate
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config_file(tmp_path_factory):
    """Write a config file that lives for the whole test module."""
    path = tmp_path_factory.mktemp("e2e") / "config.yml"
    _write_config(path)
    return path


@pytest.fixture(scope="module")
def session_id():
    """A unique session id shared across all tests in this module."""
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="class")
def droplet(config_file, session_id):
    """Create a single droplet with all features and destroy it after all tests.

    The droplet is created with DNS, a machine type (cloud-init), a custom tag,
    and --wait-for-ip so that all aspects can be verified by individual tests.
    """
    name = _unique_name()
    custom_tag = f"e2e-tag-{uuid.uuid4().hex[:6]}"

    # ---- CREATE with all features ------------------------------------------
    result = run_machine(
        "create",
        "--name",
        name,
        "--type",
        "e2e-basic",
        "--update-dns",
        "--tag",
        custom_tag,
        "--wait-for-ip",
        config_file=config_file,
        session_id=session_id,
    )
    assert result.returncode == 0, f"create failed: {result.stderr}"
    create_out = result.stdout + result.stderr
    droplet_id = _extract_droplet_id(create_out)
    assert droplet_id, f"Could not find droplet id in output:\n{create_out}"

    info = {
        "name": name,
        "id": droplet_id,
        "custom_tag": custom_tag,
        "create_out": create_out,
    }

    yield info

    # ---- TEARDOWN: destroy with DNS cleanup --------------------------------
    run_machine(
        "--verbose",
        "destroy",
        "--no-confirm",
        "--delete-dns",
        droplet_id,
        config_file=config_file,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Tests — one droplet, many assertions
# ---------------------------------------------------------------------------


class TestDropletLifecycle:
    """Create one droplet with all features and verify each aspect independently.

    A single droplet is created (via the class-scoped ``droplet`` fixture) with
    DNS, a machine type, and a custom tag.  Each test method verifies a different
    aspect so that failures are reported individually.  The droplet is destroyed
    automatically after all tests complete.
    """

    def test_droplet_appears_in_list(self, droplet, config_file, session_id):
        """Verify the droplet shows up in ``list`` with the correct name."""
        result = run_machine(
            "list",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"list failed: {result.stderr}"
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet["id"]]
        assert len(matched) == 1, f"Expected 1 droplet with id {droplet['id']}, got {len(matched)}"
        assert matched[0]["name"] == droplet["name"]

    def test_droplet_has_ip(self, droplet, config_file, session_id):
        """Verify the droplet was assigned an IP address."""
        result = run_machine(
            "list",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet["id"]]
        assert len(matched) == 1
        assert matched[0]["ip"] is not None, "Droplet has no IP address"

    def test_dns_record_created(self, droplet, config_file, session_id):
        """Verify that a DNS A record was created for the droplet."""
        result = run_machine(
            "list-domain",
            "--name",
            droplet["name"],
            "--output",
            "json",
            E2E_DNS_ZONE,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"list-domain failed: {result.stderr}"
        records = json.loads(result.stdout)
        a_records = [r for r in records if r.get("name") == droplet["name"] and r.get("type") == "A"]
        assert len(a_records) >= 1, f"No A record found for {droplet['name']}.{E2E_DNS_ZONE}"

    def test_dns_zone_in_create_output(self, droplet):
        """Verify that DNS zone was mentioned in the create output."""
        assert E2E_DNS_ZONE in droplet["create_out"], f"DNS zone not mentioned in output:\n{droplet['create_out']}"

    def test_type_tag_applied(self, droplet, config_file, session_id):
        """Verify that the machine type tag was applied and is filterable."""
        result = run_machine(
            "list",
            "--type",
            "e2e-basic",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet["id"]]
        assert len(matched) == 1, "Droplet not found when filtering by type e2e-basic"
        assert matched[0]["type"] == "e2e-basic", "Type tag mismatch"

    def test_custom_tag_applied(self, droplet, config_file, session_id):
        """Verify that the custom tag was applied and is filterable."""
        result = run_machine(
            "list",
            "--tag",
            droplet["custom_tag"],
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet["id"]]
        assert len(matched) == 1, f"Droplet not found with tag {droplet['custom_tag']}"
