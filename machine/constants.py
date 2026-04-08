import sys
from pathlib import Path

_new_config_dir = str(Path.home() / ".config" / "machine")
_old_config_dir = str(Path.home() / ".machine")


def _resolve_config_dir():
    new_path = Path(_new_config_dir)
    old_path = Path(_old_config_dir)
    if new_path.exists():
        return _new_config_dir
    if old_path.exists():
        print(
            f"Warning: config directory {_old_config_dir} is deprecated, "
            f"please move it to {_new_config_dir}",
            file=sys.stderr,
        )
        return _old_config_dir
    return _new_config_dir


default_config_dir_path = _resolve_config_dir()
default_config_file_path = default_config_dir_path + "/config.yml"
default_session_id_file_path = default_config_dir_path + "/session-id.yml"
