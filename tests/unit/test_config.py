"""Tests for software_inventory_collector.config module"""
from dataclasses import dataclass
from typing import List

import pytest

from software_inventory_collector.config import (
    Config,
    ConfigMissingKeyError,
    _BaseConfig,
)


def verify_config(config: _BaseConfig, config_data: dict):
    """Recursively match values in Config object with values in raw dict."""
    for key, value in config_data.items():
        if isinstance(value, list):
            if not isinstance(value[0], dict):
                assert config.__getattribute__(key) == value
            else:
                for sub_config, sub_data in zip(config.__getattribute__(key), value):
                    verify_config(sub_config, sub_data)
        elif isinstance(value, dict):
            verify_config(config.__getattribute__(key), value)
        else:
            assert config.__getattribute__(key) == value


def test_config_parsing_success(collector_config_data):
    """Test parsing collector's Config object from dictionary data."""
    config = Config.from_dict(collector_config_data)
    verify_config(config, collector_config_data)


def test_config_parsing_missing(collector_config_data):
    """Test that exception is raised if required key is missing"""
    del collector_config_data["settings"]["site"]

    with pytest.raises(ConfigMissingKeyError):
        Config.from_dict(collector_config_data)


def test_config_parsing_basic_list():
    """Test parsing config object that contains list of basic objects (int/str/..)

    As this use-case does not exist in the default collector's config, this test will
    create its own config definition.
    """

    @dataclass
    class ConfigWithList(_BaseConfig):
        strings: List[str]
        numbers: List[int]

    raw_config = {"strings": ["hello", "world"], "numbers": [1, 2, 3]}

    config = ConfigWithList.from_dict(raw_config)
    verify_config(config, raw_config)
