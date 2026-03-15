"""End-to-end tests that create real VMs on DigitalOcean.

These tests require a real DigitalOcean environment and are NOT run as part of
the normal test suite. They must be invoked explicitly:

    uv run pytest tests/test_e2e.py -v

Required environment variables:
    E2E_DO_TOKEN    - DigitalOcean API token
    E2E_SSH_KEY     - Name of an SSH key already registered in DO
    E2E_DNS_ZONE    - DNS zone managed by DO (e.g. "test.example.com")

Optional environment variables:
    E2E_REGION      - Region slug (default: nyc1)
    E2E_IMAGE       - Image slug (default: ubuntu-24-04-x64)
    E2E_SIZE        - Machine size slug (default: s-1vcpu-512mb-10gb)
    E2E_PROJECT     - DO project name to assign droplets to
"""

import json
import os
import subprocess
import textwrap
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
E2E_PROJECT = os.environ.get("E2E_PROJECT", "")

pytestmark = pytest.mark.e2e

_MISSING = []
if not E2E_DO_TOKEN:
    _MISSING.append("E2E_DO_TOKEN")
if not E2E_SSH_KEY:
    _MISSING.append("E2E_SSH_KEY")
if not E2E_DNS_ZONE:
    _MISSING.append("E2E_DNS_ZONE")

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
    if E2E_PROJECT:
        cfg["project"] = E2E_PROJECT
    cfg.update(overrides)

    do_lines = "\n".join(f"  {k}: {v}" for k, v in cfg.items())
    content = textwrap.dedent(
        f"""\
        digital-ocean:
        {do_lines}
        machines:
          e2e-basic:
            new-user-name: e2euser
        """
    )
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


@pytest.fixture()
def droplet_cleanup(config_file, session_id):
    """Fixture that tracks created droplet IDs and destroys them after the test."""
    created_ids = []
    yield created_ids
    for did in created_ids:
        run_machine(
            "--verbose",
            "destroy",
            "--no-confirm",
            str(did),
            config_file=config_file,
            session_id=session_id,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDropletLifecycle:
    """Create a droplet, verify it, then destroy it."""

    def test_create_and_list_and_destroy(self, config_file, session_id, droplet_cleanup):
        name = _unique_name()

        # ---- CREATE --------------------------------------------------------
        result = run_machine(
            "create",
            "--name",
            name,
            "--no-initialize",
            "--wait-for-ip",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"create failed: {result.stderr}"
        # Extract the droplet id from output like "New droplet created with id: 12345"
        create_out = result.stdout + result.stderr
        droplet_id = None
        for line in create_out.splitlines():
            if "id:" in line.lower():
                # grab the number after "id:"
                parts = line.split("id:")
                if len(parts) >= 2:
                    candidate = parts[-1].strip()
                    if candidate.isdigit():
                        droplet_id = candidate
                        break
        assert droplet_id, f"Could not find droplet id in output:\n{create_out}"
        droplet_cleanup.append(droplet_id)

        # ---- LIST ----------------------------------------------------------
        result = run_machine(
            "list",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"list failed: {result.stderr}"
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet_id]
        assert len(matched) == 1, f"Expected 1 droplet with id {droplet_id}, got {len(matched)}"
        assert matched[0]["name"] == name
        assert matched[0]["ip"] is not None

        # ---- DESTROY -------------------------------------------------------
        result = run_machine(
            "destroy",
            "--no-confirm",
            droplet_id,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"destroy failed: {result.stderr}"
        # Remove from cleanup list since we already destroyed it
        droplet_cleanup.remove(droplet_id)

        # ---- VERIFY GONE ---------------------------------------------------
        result = run_machine(
            "list",
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet_id]
        assert len(matched) == 0, "Droplet still exists after destroy"


class TestDNSLifecycle:
    """Create a droplet with DNS, verify the record, then destroy and verify cleanup."""

    def test_create_with_dns_and_destroy(self, config_file, session_id, droplet_cleanup):
        name = _unique_name()

        # ---- CREATE with DNS -----------------------------------------------
        result = run_machine(
            "create",
            "--name",
            name,
            "--no-initialize",
            "--update-dns",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"create failed: {result.stderr}"
        create_out = result.stdout + result.stderr
        droplet_id = None
        for line in create_out.splitlines():
            if "id:" in line.lower():
                parts = line.split("id:")
                if len(parts) >= 2:
                    candidate = parts[-1].strip()
                    if candidate.isdigit():
                        droplet_id = candidate
                        break
        assert droplet_id, f"Could not find droplet id in output:\n{create_out}"
        droplet_cleanup.append(droplet_id)

        # Verify DNS was mentioned in output
        assert E2E_DNS_ZONE in create_out, f"DNS zone not mentioned in output:\n{create_out}"

        # ---- LIST DOMAIN ---------------------------------------------------
        result = run_machine(
            "list-domain",
            "--name",
            name,
            "--output",
            "json",
            E2E_DNS_ZONE,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"list-domain failed: {result.stderr}"
        records = json.loads(result.stdout)
        a_records = [r for r in records if r.get("name") == name and r.get("type") == "A"]
        assert len(a_records) >= 1, f"No A record found for {name}.{E2E_DNS_ZONE}"

        # ---- DESTROY with DNS cleanup --------------------------------------
        result = run_machine(
            "destroy",
            "--no-confirm",
            "--delete-dns",
            droplet_id,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"destroy failed: {result.stderr}"
        droplet_cleanup.remove(droplet_id)

        # ---- VERIFY DNS RECORD REMOVED -------------------------------------
        result = run_machine(
            "list-domain",
            "--name",
            name,
            "--all",
            "--output",
            "json",
            E2E_DNS_ZONE,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        records = json.loads(result.stdout)
        a_records = [r for r in records if r.get("name") == name and r.get("type") == "A"]
        assert len(a_records) == 0, f"DNS A record still exists for {name}.{E2E_DNS_ZONE}"


class TestCreateWithInitialize:
    """Create a droplet with cloud-init and verify it was initialized."""

    def test_create_with_type(self, config_file, session_id, droplet_cleanup):
        name = _unique_name()

        # ---- CREATE with initialization ------------------------------------
        result = run_machine(
            "create",
            "--name",
            name,
            "--type",
            "e2e-basic",
            "--wait-for-ip",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"create failed: {result.stderr}"
        create_out = result.stdout + result.stderr
        droplet_id = None
        for line in create_out.splitlines():
            if "id:" in line.lower():
                parts = line.split("id:")
                if len(parts) >= 2:
                    candidate = parts[-1].strip()
                    if candidate.isdigit():
                        droplet_id = candidate
                        break
        assert droplet_id, f"Could not find droplet id in output:\n{create_out}"
        droplet_cleanup.append(droplet_id)

        # ---- VERIFY TYPE TAG -----------------------------------------------
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
        matched = [d for d in droplets if str(d["id"]) == droplet_id]
        assert len(matched) == 1
        assert matched[0]["type"] == "e2e-basic"

        # ---- CLEANUP -------------------------------------------------------
        result = run_machine(
            "destroy",
            "--no-confirm",
            droplet_id,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"destroy failed: {result.stderr}"
        droplet_cleanup.remove(droplet_id)


class TestCustomTag:
    """Verify that custom tags are applied to created droplets."""

    def test_custom_tag(self, config_file, session_id, droplet_cleanup):
        name = _unique_name()
        custom_tag = f"e2e-tag-{uuid.uuid4().hex[:6]}"

        result = run_machine(
            "create",
            "--name",
            name,
            "--no-initialize",
            "--tag",
            custom_tag,
            "--wait-for-ip",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0, f"create failed: {result.stderr}"
        create_out = result.stdout + result.stderr
        droplet_id = None
        for line in create_out.splitlines():
            if "id:" in line.lower():
                parts = line.split("id:")
                if len(parts) >= 2:
                    candidate = parts[-1].strip()
                    if candidate.isdigit():
                        droplet_id = candidate
                        break
        assert droplet_id
        droplet_cleanup.append(droplet_id)

        # Verify tag via list --tag filter
        result = run_machine(
            "list",
            "--tag",
            custom_tag,
            "--output",
            "json",
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        droplets = json.loads(result.stdout)
        matched = [d for d in droplets if str(d["id"]) == droplet_id]
        assert len(matched) == 1, f"Droplet not found with tag {custom_tag}"

        # Cleanup
        result = run_machine(
            "destroy",
            "--no-confirm",
            droplet_id,
            config_file=config_file,
            session_id=session_id,
        )
        assert result.returncode == 0
        droplet_cleanup.remove(droplet_id)
