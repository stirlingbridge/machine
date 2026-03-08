"""Integration tests that run the machine CLI as a subprocess, the same way a user would."""

import os
import subprocess
import textwrap
import pytest


def run_machine(*args, env_override=None):
    """Run the machine CLI as a subprocess and return the result."""
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        ["uv", "run", "machine"] + list(args),
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def write_config(path, content):
    with open(path, "w") as f:
        f.write(textwrap.dedent(content))


class TestVersionCommand:
    """Smoke test: the CLI runs and the version command works without any config."""

    def test_version_runs(self):
        result = run_machine("version")
        assert result.returncode == 0
        assert result.stdout.strip()  # prints something

    def test_help_runs(self):
        result = run_machine("--help")
        assert result.returncode == 0
        assert "Usage" in result.stdout


class TestEnvVarExpansionIntegration:
    """End-to-end tests that verify environment variable expansion works
    when the actual machine tool is invoked with a config file."""

    @pytest.fixture()
    def config_dir(self, tmp_path):
        return tmp_path

    def test_env_var_expanded_in_config(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: "${TEST_DO_TOKEN}"
              ssh-key: test-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              test-machine:
                new-user-name: testuser
            """,
        )
        result = run_machine(
            "--debug",
            "--config-file",
            str(config_file),
            "types",
            env_override={"TEST_DO_TOKEN": "tok_secret_12345"},
        )
        assert result.returncode == 0
        # The debug output on stderr should contain the expanded token value
        assert "tok_secret_12345" in result.stderr
        # And should NOT contain the unexpanded variable reference
        assert "${TEST_DO_TOKEN}" not in result.stderr
        # The types command should list the machine name on stdout
        assert "test-machine" in result.stdout

    def test_multiple_env_vars_expanded(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: "${TEST_TOKEN}"
              ssh-key: "${TEST_SSH_KEY}"
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              dev:
                new-user-name: devuser
            """,
        )
        result = run_machine(
            "--debug",
            "--config-file",
            str(config_file),
            "types",
            env_override={"TEST_TOKEN": "expanded_token", "TEST_SSH_KEY": "expanded_key"},
        )
        assert result.returncode == 0
        assert "expanded_token" in result.stderr
        assert "expanded_key" in result.stderr

    def test_env_var_with_default_uses_default_when_unset(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key: test-key
              machine-size: "${TEST_SIZE:-s-2vcpu-4gb}"
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              myvm:
                new-user-name: admin
            """,
        )
        # Make sure TEST_SIZE is not in the environment
        clean_env = os.environ.copy()
        clean_env.pop("TEST_SIZE", None)
        result = run_machine(
            "--debug",
            "--config-file",
            str(config_file),
            "types",
            env_override={},
        )
        # Run with TEST_SIZE explicitly removed
        result = subprocess.run(
            ["uv", "run", "machine", "--debug", "--config-file", str(config_file), "types"],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert result.returncode == 0
        assert "s-2vcpu-4gb" in result.stderr

    def test_env_var_with_default_uses_value_when_set(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key: test-key
              machine-size: "${TEST_SIZE:-s-2vcpu-4gb}"
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              myvm:
                new-user-name: admin
            """,
        )
        result = run_machine(
            "--debug",
            "--config-file",
            str(config_file),
            "types",
            env_override={"TEST_SIZE": "s-4vcpu-8gb"},
        )
        assert result.returncode == 0
        assert "s-4vcpu-8gb" in result.stderr
        assert "s-2vcpu-4gb" not in result.stderr

    def test_missing_env_var_without_default_exits_with_error(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: "${DEFINITELY_NOT_SET_VAR}"
              ssh-key: test-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              myvm:
                new-user-name: admin
            """,
        )
        clean_env = os.environ.copy()
        clean_env.pop("DEFINITELY_NOT_SET_VAR", None)
        result = subprocess.run(
            ["uv", "run", "machine", "--config-file", str(config_file), "types"],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert result.returncode != 0
        assert "DEFINITELY_NOT_SET_VAR" in result.stderr

    def test_env_var_in_machine_config_section(self, config_dir):
        config_file = config_dir / "config.yml"
        write_config(
            config_file,
            """\
            digital-ocean:
              access-token: fake-token
              ssh-key: test-key
              machine-size: s-1vcpu-1gb
              image: ubuntu-22-04-x64
              region: nyc1
              project: test-project
            machines:
              web-server:
                new-user-name: "${TEST_USERNAME}"
              db-server:
                new-user-name: admin
            """,
        )
        result = run_machine(
            "--debug",
            "--config-file",
            str(config_file),
            "types",
            env_override={"TEST_USERNAME": "deploy_user"},
        )
        assert result.returncode == 0
        assert "deploy_user" in result.stderr
        # Both machine types should be listed
        assert "db-server" in result.stdout
        assert "web-server" in result.stdout
