"""Tests for software_inventory_collector.cli module"""
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import yaml

from software_inventory_collector import cli


@pytest.mark.parametrize("dry_run", [True, False])
def test_parse_cli(dry_run, mocker):
    """Test CLI argument parsing."""
    conf_path = "/path/to/conf"
    argv = ["software-inventory-collector", "-c", conf_path]
    if dry_run:
        argv.append("--dry-run")
    mocker.patch("sys.argv", argv)

    parsed_args = cli.parse_cli()

    assert parsed_args.dry_run == dry_run
    assert parsed_args.config == conf_path


def test_parse_config_success(mocker):
    """Test successfully parsing config and returning Config object."""
    conf_file_path = "/path/to/config"
    conf_file_content = {"option": "value"}
    conf_file_raw_content = yaml.dump(conf_file_content)
    expected_config = MagicMock()
    from_dict_mock = mocker.patch.object(
        cli.Config, "from_dict", return_value=expected_config
    )

    with patch("builtins.open", mock_open(read_data=conf_file_raw_content)) as mock_file:
        config = cli.parse_config(conf_file_path)

    mock_file.assert_called_once_with(conf_file_path, "r", encoding="UTF-8")
    from_dict_mock.assert_called_once_with(conf_file_content)
    assert config is expected_config


@pytest.mark.parametrize(
    "exception, expected_msg",
    [
        (cli.yaml.YAMLError, "Failed to parse config file"),
        (IOError, "Failed to read config file"),
        (cli.ConfigMissingKeyError("req_key"), "Config is missing required key"),
    ],
)
def test_parse_config_fail(exception, expected_msg, mocker):
    """Test handling of various exceptions when parsing config."""
    config_data = "option: value"
    mocker.patch.object(cli.Config, "from_dict", side_effect=exception)

    with patch("builtins.open", mock_open(read_data=config_data)):
        with pytest.raises(cli.ConfigError) as exc:
            cli.parse_config("/path/to/config")
        assert str(exc.value).startswith(expected_msg)


@pytest.mark.parametrize("dry_run", [True, False])
def test_cli_main_success(dry_run, mocker):
    """Test successfully running 'main' function."""
    conf_path = "/path/to/conf"
    cli_args = MagicMock()
    cli_args.config = conf_path
    cli_args.dry_run = dry_run

    controller_disconnect = AsyncMock()
    controller = MagicMock()
    controller.disconnect.side_effect = controller_disconnect

    config = MagicMock()

    parse_cli_mock = mocker.patch.object(cli, "parse_cli", return_value=cli_args)
    parse_config_mock = mocker.patch.object(cli, "parse_config", return_value=config)
    get_controller_mock = mocker.patch.object(
        cli, "get_controller", return_value=controller
    )
    get_exporter_data_mock = mocker.patch.object(cli, "get_exporter_data")
    get_juju_data_mock = mocker.patch.object(cli, "get_juju_data")

    with pytest.raises(SystemExit) as exc:
        cli.main()

    parse_cli_mock.assert_called_once()
    parse_config_mock.assert_called_once_with(conf_path)
    get_controller_mock.assert_called_once_with(config)
    if not dry_run:
        get_exporter_data_mock.assert_called_once_with(config)
        get_juju_data_mock.assert_called_once_with(config, controller)
    else:
        get_exporter_data_mock.assert_not_called()
        get_juju_data_mock.assert_not_called()

    controller_disconnect.assert_called_once()

    assert exc.value.code == 0


def test_cli_main_config_error(mocker):
    """Test failure of main function during config loading."""
    conf_path = "/path/to/conf"
    cli_args = MagicMock()
    cli_args.config = conf_path

    mocker.patch.object(cli, "parse_cli", return_value=cli_args)
    parse_config_mock = mocker.patch.object(
        cli, "parse_config", side_effect=cli.ConfigError
    )
    get_controller_mock = mocker.patch.object(cli, "get_controller")
    get_exporter_data_mock = mocker.patch.object(cli, "get_exporter_data")
    get_juju_data_mock = mocker.patch.object(cli, "get_juju_data")

    with pytest.raises(SystemExit) as exc:
        cli.main()

    parse_config_mock.assert_called_once_with(conf_path)
    get_controller_mock.assert_not_called()
    get_exporter_data_mock.assert_not_called()
    get_juju_data_mock.assert_not_called()
    assert exc.value.code == 1


def test_cli_main_juju_error(mocker):
    """Test failure of main function during connection to juju controller."""
    conf_path = "/path/to/conf"
    cli_args = MagicMock()
    cli_args.config = conf_path
    config = MagicMock()

    mocker.patch.object(cli, "parse_cli", return_value=cli_args)
    parse_config_mock = mocker.patch.object(cli, "parse_config", return_value=config)
    get_controller_mock = mocker.patch.object(
        cli, "get_controller", side_effect=cli.JujuError
    )
    get_exporter_data_mock = mocker.patch.object(cli, "get_exporter_data")
    get_juju_data_mock = mocker.patch.object(cli, "get_juju_data")

    with pytest.raises(SystemExit) as exc:
        cli.main()

    parse_config_mock.assert_called_once_with(conf_path)
    get_controller_mock.assert_called_once_with(config)
    get_exporter_data_mock.assert_not_called()
    get_juju_data_mock.assert_not_called()
    assert exc.value.code == 1


def test_cli_main_collection_error(mocker):
    """Test failure of main function during data collection."""
    conf_path = "/path/to/conf"
    cli_args = MagicMock()
    cli_args.config = conf_path
    cli_args.dry_run = False

    controller_disconnect = AsyncMock()
    controller = MagicMock()
    controller.disconnect.side_effect = controller_disconnect

    config = MagicMock()

    parse_cli_mock = mocker.patch.object(cli, "parse_cli", return_value=cli_args)
    parse_config_mock = mocker.patch.object(cli, "parse_config", return_value=config)
    get_controller_mock = mocker.patch.object(
        cli, "get_controller", return_value=controller
    )
    get_exporter_data_mock = mocker.patch.object(
        cli, "get_exporter_data", side_effect=Exception
    )
    get_juju_data_mock = mocker.patch.object(cli, "get_juju_data")

    with pytest.raises(SystemExit) as exc:
        cli.main()

    parse_cli_mock.assert_called_once()
    parse_config_mock.assert_called_once_with(conf_path)
    get_controller_mock.assert_called_once_with(config)
    get_exporter_data_mock.assert_called_once_with(config)
    get_juju_data_mock.assert_not_called()

    controller_disconnect.assert_called_once()

    assert exc.value.code == 1
