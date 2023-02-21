"""Module containing software-inventory-collector configuration classes."""
from dataclasses import dataclass, fields
from typing import ClassVar, Dict, List, get_args, get_origin

from typing_extensions import Self

from software_inventory_collector.exception import ConfigMissingKeyError


@dataclass
class _BaseConfig:
    NAME: ClassVar[str] = ""

    @classmethod
    def from_dict(cls, source: Dict) -> Self:
        """Factory method that creates config object from raw config data.

        This method finds values for each dataclass attributes specified in the class.
        It's designed to handle:
            * direct values (key: value)
            * list of simple values (key: [value1, value2])
            * simple nested config structures (section_name: {<section_configs>})
            * list of nested config structures (section_name:
                [{section_config}, {section_config}]

        :param source: Dict data from config to populate specific config subsection.
        :return: Initiated instance of the class.
        """
        kwargs = {}
        try:
            for field in fields(cls):
                origin_type = get_origin(field.type)
                value = source[field.name]
                if origin_type == list:
                    # Handle lists of simple and nested config values
                    nested_type = get_args(field.type)[0]
                    if issubclass(nested_type, _BaseConfig):
                        kwargs[field.name] = [nested_type(**value) for value in value]
                    else:
                        kwargs[field.name] = value
                elif issubclass(field.type, _BaseConfig):
                    kwargs[field.name] = field.type.from_dict(value)  # type: ignore
                else:
                    kwargs[field.name] = value
        except KeyError as exc:
            raise ConfigMissingKeyError(f"{cls.NAME}.{exc.args[0]}") from exc

        return cls(**kwargs)


@dataclass
class _ConfigSettings(_BaseConfig):
    """Definition for 'settings' subsection of main config."""

    NAME = "settings"

    collection_path: str
    customer: str
    site: str


@dataclass
class _ConfigTarget(_BaseConfig):
    """Definition for 'target' subsection of main config."""

    NAME = "target"

    endpoint: str
    hostname: str
    customer: str
    site: str
    model: str


@dataclass
class _ConfigJujuController(_BaseConfig):
    """Definition for 'juju_controller' subsection of main config."""

    NAME = "juju_controller"

    endpoint: str
    ca_cert: str
    username: str
    password: str


@dataclass
class Config(_BaseConfig):
    """Object representation of a complete config file."""

    settings: _ConfigSettings
    targets: List[_ConfigTarget]
    juju_controller: _ConfigJujuController
