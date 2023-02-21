#!/usr/bin/env python3
"""CLI Entrypoint to the software-inventory-collector."""
import argparse
import sys

import yaml
from juju import jasyncio
from juju.controller import Controller
from juju.errors import JujuError

from software_inventory_collector.collector import (
    get_controller,
    get_exporter_data,
    get_juju_data,
)
from software_inventory_collector.config import Config
from software_inventory_collector.exception import ConfigError, ConfigMissingKeyError


def parse_cli() -> argparse.Namespace:
    """Parse CLI arguments."""
    arg_parser = argparse.ArgumentParser("Collect software inventory data")
    arg_parser.add_argument(
        "-c",
        "--config",
        help="Configuration file path.",
        default="/var/snap/software-inventory-collector/current/config.yaml",
    )
    arg_parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=False,
        help="Verifies successful connection to the controller but no output "
        "is produced.",
    )
    return arg_parser.parse_args()


def parse_config(config_path: str) -> Config:
    """Load and parse application config file.

    :param config_path: Path to the application config
    :return: `Config` object holding application configuration
    """
    try:
        with open(config_path, "r", encoding="UTF-8") as conf_file:
            config_data = yaml.safe_load(conf_file)
            config = Config.from_dict(config_data)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse config file: {exc}") from exc
    except IOError as exc:
        raise ConfigError(f"Failed to read config file '{config_path}'") from exc
    except ConfigMissingKeyError as exc:
        raise ConfigError(f"Config is missing required key '{exc.key_name}'") from exc

    return config


def main() -> None:
    """Run software inventory collector."""
    args = parse_cli()

    try:
        config = parse_config(args.config)
    except ConfigError as exc:
        print(f"Failed to load config: {exc}")
        sys.exit(1)

    try:
        controller: Controller = jasyncio.run(get_controller(config))
    except JujuError as exc:
        print(f"Failed to connect to juju controller: {exc}")
        sys.exit(1)

    if args.dry_run:
        jasyncio.run(controller.disconnect())
        print("OK.")
        sys.exit(0)

    try:
        get_exporter_data(config)
        jasyncio.run(get_juju_data(config, controller))
        exit_code = 0
    except Exception as exc:  # pylint: disable=W0718
        print(f"Failed to collect data: {exc}")
        exit_code = 1
    finally:
        jasyncio.run(controller.disconnect())

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
