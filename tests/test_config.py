import os
import pytest
from unittest.mock import patch
from machine.config import _expand_env_vars, _get_machine_sizes, _get_regions, _get_ssh_keys


class TestExpandEnvVars:
    def test_plain_string_unchanged(self):
        assert _expand_env_vars("hello world") == "hello world"

    def test_non_string_types_unchanged(self):
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(3.14) == 3.14
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None

    def test_simple_variable_substitution(self):
        with patch.dict(os.environ, {"MY_VAR": "my_value"}):
            assert _expand_env_vars("${MY_VAR}") == "my_value"

    def test_variable_embedded_in_string(self):
        with patch.dict(os.environ, {"HOST": "example.com"}):
            assert _expand_env_vars("https://${HOST}/api") == "https://example.com/api"

    def test_multiple_variables_in_string(self):
        with patch.dict(os.environ, {"HOST": "example.com", "PORT": "8080"}):
            assert _expand_env_vars("${HOST}:${PORT}") == "example.com:8080"

    def test_default_value_when_var_unset(self):
        env = os.environ.copy()
        env.pop("UNSET_VAR", None)
        with patch.dict(os.environ, env, clear=True):
            assert _expand_env_vars("${UNSET_VAR:-fallback}") == "fallback"

    def test_default_value_ignored_when_var_set(self):
        with patch.dict(os.environ, {"MY_VAR": "actual"}):
            assert _expand_env_vars("${MY_VAR:-fallback}") == "actual"

    def test_default_value_empty_string(self):
        env = os.environ.copy()
        env.pop("UNSET_VAR", None)
        with patch.dict(os.environ, env, clear=True):
            assert _expand_env_vars("${UNSET_VAR:-}") == ""

    def test_unset_variable_without_default_exits(self):
        env = os.environ.copy()
        env.pop("MISSING_VAR", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit):
                _expand_env_vars("${MISSING_VAR}")

    def test_dict_values_expanded(self):
        with patch.dict(os.environ, {"TOKEN": "secret123"}):
            data = {"key": "${TOKEN}", "plain": "no-change"}
            result = _expand_env_vars(data)
            assert result == {"key": "secret123", "plain": "no-change"}

    def test_nested_dict_expanded(self):
        with patch.dict(os.environ, {"VAL": "deep"}):
            data = {"outer": {"inner": "${VAL}"}}
            result = _expand_env_vars(data)
            assert result == {"outer": {"inner": "deep"}}

    def test_list_values_expanded(self):
        with patch.dict(os.environ, {"A": "x", "B": "y"}):
            data = ["${A}", "literal", "${B}"]
            result = _expand_env_vars(data)
            assert result == ["x", "literal", "y"]

    def test_mixed_nested_structure(self):
        with patch.dict(os.environ, {"V": "replaced"}):
            data = {"list": ["${V}", "fixed"], "nested": {"k": "${V}"}}
            result = _expand_env_vars(data)
            assert result == {"list": ["replaced", "fixed"], "nested": {"k": "replaced"}}


class TestGetSshKeys:
    """The 'ssh-key' config value accepts either a single name or a list of
    names; both forms normalize to a non-empty list."""

    def test_single_name_returns_one_element_list(self):
        assert _get_ssh_keys({"ssh-key": "my-key"}, "digital-ocean") == ["my-key"]

    def test_list_of_names_preserved(self):
        assert _get_ssh_keys({"ssh-key": ["alice", "bob"]}, "digital-ocean") == ["alice", "bob"]

    def test_list_elements_coerced_to_str(self):
        assert _get_ssh_keys({"ssh-key": [1, 2]}, "digital-ocean") == ["1", "2"]

    def test_missing_key_exits(self):
        with pytest.raises(SystemExit):
            _get_ssh_keys({}, "digital-ocean")

    def test_empty_list_exits(self):
        with pytest.raises(SystemExit):
            _get_ssh_keys({"ssh-key": []}, "digital-ocean")

    def test_unsupported_type_exits(self):
        with pytest.raises(SystemExit):
            _get_ssh_keys({"ssh-key": {"unexpected": "mapping"}}, "digital-ocean")


class TestGetRegions:
    """The 'region' config value accepts either a single region or a list of
    regions to try in order; both forms normalize to a non-empty list."""

    def test_single_region_returns_one_element_list(self):
        assert _get_regions({"region": "nyc3"}, "digital-ocean") == ["nyc3"]

    def test_list_of_regions_keeps_order(self):
        assert _get_regions({"region": ["nyc3", "nyc1", "tor1"]}, "digital-ocean") == ["nyc3", "nyc1", "tor1"]

    def test_missing_key_exits(self):
        with pytest.raises(SystemExit):
            _get_regions({}, "digital-ocean")

    def test_empty_list_exits(self):
        with pytest.raises(SystemExit):
            _get_regions({"region": []}, "digital-ocean")

    def test_unsupported_type_exits(self):
        with pytest.raises(SystemExit):
            _get_regions({"region": {"unexpected": "mapping"}}, "digital-ocean")


class TestGetMachineSizes:
    """The 'machine-size' config value accepts either a single size or a list
    of sizes to try in order."""

    def test_single_size_returns_one_element_list(self):
        assert _get_machine_sizes({"machine-size": "s-4vcpu-8gb"}, "digital-ocean") == ["s-4vcpu-8gb"]

    def test_list_of_sizes_keeps_order(self):
        sizes = ["s-4vcpu-8gb-intel", "s-4vcpu-8gb-amd"]
        assert _get_machine_sizes({"machine-size": sizes}, "digital-ocean") == sizes

    def test_empty_list_exits(self):
        with pytest.raises(SystemExit):
            _get_machine_sizes({"machine-size": []}, "digital-ocean")
