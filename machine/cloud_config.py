import shlex

from expandvars import expand

from machine.log import fatal_error
from machine.provider import CloudProvider
from machine.types import MachineConfig


def _render_script_args(script_args, cloud_env) -> str:
    """Render config script-args for interpolation into the runcmd shell string.

    A string value is passed through verbatim (legacy behavior). A list value
    is rendered so that each element reaches the script as exactly one shell
    argument, however many spaces or quotes it contains. In both cases the
    result is escaped for the YAML double-quoted scalar it is embedded in.
    """
    if not script_args:
        return ""
    if isinstance(script_args, list):
        expanded = [expand(str(item), environ=cloud_env) for item in script_args]
        quoted = " ".join(shlex.quote(item) for item in expanded)
        return quoted.replace("\\", "\\\\").replace('"', '\\"')
    escaped = str(script_args).replace('"', '\\"')
    # Expand here because otherwise escaping the vars properly for nested scripts is a guessing game
    return expand(escaped, environ=cloud_env)


def get_user_data(provider: CloudProvider, ssh_key_names: list, fqdn: str, machine_config: MachineConfig):
    if not fqdn:
        fqdn = ""

    public_keys = []
    for ssh_key_name in ssh_key_names:
        ssh_key = provider.get_ssh_key(ssh_key_name)
        if not ssh_key:
            fatal_error(f"Error: SSH key '{ssh_key_name}' not found in {provider.provider_name}")
        public_keys.append(ssh_key.public_key)

    cloud_env = {
        "MACHINE_SCRIPT_URL": machine_config.script_url,
        "MACHINE_SCRIPT_DIR": machine_config.script_dir,
        "MACHINE_FQDN": fqdn,
    }

    escaped_args = _render_script_args(machine_config.script_args, cloud_env)
    authorized_keys = "\n".join(f"      - {key}" for key in public_keys)
    cloud_config = f"""#cloud-config
users:
  - name: {machine_config.new_user_name}
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh-authorized-keys:
{authorized_keys}
"""
    if machine_config.script_url and machine_config.script_dir and machine_config.script_path:
        cloud_config += f"""
runcmd:
  - mkdir -p {machine_config.script_dir}
  - curl -L {machine_config.script_url} -o {machine_config.script_path}
  - chmod +x {machine_config.script_path}
  - [su, -c, "env {" ".join([f"{k}='{v}'" for k, v in cloud_env.items()])} {machine_config.script_path} {escaped_args}", -, {machine_config.new_user_name}]
"""
    return cloud_config
