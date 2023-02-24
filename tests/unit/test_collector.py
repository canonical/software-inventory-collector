"""Tests for software_inventory_collector.collector module"""
import os.path
from collections import defaultdict
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from software_inventory_collector import collector


def test_add_file_to_tar(mocker):
    """Test function that writes content to temp file and adds it to tar."""
    file_name = "collected_data_file"
    file_content = "collected data"
    tar_file_path = "/path/to/tarball"

    opened_tar = MagicMock()
    tar_object_mock = MagicMock()
    tar_object_mock.__enter__.return_value = opened_tar

    temp_file = NamedTemporaryFile()
    temp_file_write_mock = mocker.patch.object(temp_file, "write")

    mocker.patch.object(collector, "NamedTemporaryFile", return_value=temp_file)

    with patch.object(
        collector.tarfile, "open", return_value=tar_object_mock
    ) as tar_file_mock:
        collector._add_file_to_tar(file_name, file_content, tar_file_path)

    temp_file_write_mock.assert_called_once_with(file_content.encode("UTF-8"))
    tar_file_mock.assert_called_once_with(tar_file_path, "a", encoding="UTF-8")
    opened_tar.add.assert_called_once_with(temp_file.name, arcname=file_name)


def test_fetch_exporter_data_success(collector_config, mocker):
    """Test function gathering data from exporter endpoints."""
    expected_requests = []
    expected_responses = []
    expected_tar_calls = []
    ts = collector.TIMESTAMP
    output_dir = collector_config.settings.collection_path
    for target in collector_config.targets:
        tar_path = (
            f"{output_dir}/{target.customer}_@_{target.site}_@_{target.model}_@_{ts}.tar"
        )
        for endpoint in collector.ENDPOINTS:
            url = f"http://{target.endpoint}/{endpoint}"
            file_path = f"{endpoint}_@_{target.hostname}_@_{ts}"
            response = MagicMock()
            response.text = f"{target.endpoint}/{endpoint} response"
            expected_responses.append(response)
            expected_requests.append(call(url, timeout=60))
            expected_tar_calls.append(call(file_path, response.text, tar_path))

    get_mock = mocker.patch.object(
        collector.requests, "get", side_effect=expected_responses
    )
    add_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")

    collector.fetch_exporter_data(collector_config)

    get_mock.assert_has_calls(expected_requests)
    add_tar_mock.assert_has_calls(expected_tar_calls)


def test_fetch_exporter_data_error(collector_config, mocker):
    """Test handling of error during collection of data from exporter endpoint."""
    exception = collector.requests.RequestException

    mocker.patch.object(collector.requests, "get", side_effect=exception)
    add_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")

    with pytest.raises(collector.CollectionError):
        collector.fetch_exporter_data(collector_config)

    add_tar_mock.assert_not_called()


@pytest.mark.asyncio
async def test_get_controller(collector_config, mocker):
    """Test getting and connecting to the controller."""
    controller_mock = MagicMock()
    controller_connect_mock = AsyncMock()
    controller_mock.connect.side_effect = controller_connect_mock

    mocker.patch.object(collector, "Controller", return_value=controller_mock)

    connected_controller = await collector.get_controller(collector_config)

    assert connected_controller is controller_mock
    controller_mock.connect.assert_called_once_with(
        endpoint=collector_config.juju_controller.endpoint,
        username=collector_config.juju_controller.username,
        password=collector_config.juju_controller.password,
        cacert=collector_config.juju_controller.ca_cert,
    )


@pytest.mark.parametrize(
    "exported_bundle",
    [
        "bundle: bundle_data",  # Regular bundle
        "bundle: bundle_data\n---\noffers: cmr_data",  # Bundle with CMR
    ],
)
@pytest.mark.asyncio
async def test_save_bundle_data(exported_bundle, mocker):
    """Test function that saves exported juju bundles.

    This tests has two scenarios:
      * Export of a regular model bundle
      * Export of a bundle with Cross Model Relations. CMR data is expected to be skipped
    """
    expected_saved_bundle = '{"bundle": "bundle_data"}'
    add_to_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")
    bundle_name = "juju_bundle.json"
    tar_file = "/path/to.tar"
    model_mock = MagicMock()
    model_mock.export_bundle.side_effect = AsyncMock(return_value=exported_bundle)

    await collector._save_bundle_data(model_mock, bundle_name, tar_file)

    model_mock.export_bundle.assert_called_once()
    add_to_tar_mock.assert_called_once_with(bundle_name, expected_saved_bundle, tar_file)


@pytest.mark.asyncio
async def test_save_bundle_data_empty_model(mocker):
    """Test that _save_bundle_data function handles errors when exporting empty model."""
    add_to_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")
    bundle_name = "empty_bundle.json"
    tar_path = "/path/to.tar"
    expected_bundle_data = "{}"

    juju_err = defaultdict(str)
    juju_err["error"] = "nothing to export as there are no applications"
    empty_model_err = collector.JujuAPIError(juju_err)

    model_mock = MagicMock()
    model_mock.export_bundle.side_effect = AsyncMock(side_effect=empty_model_err)

    await collector._save_bundle_data(model_mock, bundle_name, tar_path)

    model_mock.export_bundle.assert_called_once()
    add_to_tar_mock.assert_called_once_with(bundle_name, expected_bundle_data, tar_path)


@pytest.mark.asyncio
async def test_save_bundle_data_err(mocker):
    """Test that _save_bundle_data function re-raises general JujuErrors"""
    add_to_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")

    juju_err = defaultdict(str)
    juju_err["error"] = "Something bad happened"
    empty_model_err = collector.JujuAPIError(juju_err)

    model_mock = MagicMock()
    model_mock.export_bundle.side_effect = AsyncMock(side_effect=empty_model_err)

    with pytest.raises(collector.JujuAPIError):
        await collector._save_bundle_data(model_mock, "bundle_name", "tar_path")

    add_to_tar_mock.assert_not_called()


@pytest.mark.asyncio
async def test_save_status_data(mocker):
    add_to_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")
    status_name = "model_status.json"
    tar_path = "/path/to.tar"
    status_data = "{'status': 'data'}"

    status_mock = MagicMock()
    status_mock.to_json.return_value = status_data

    model_mock = MagicMock()
    model_mock.get_status.side_effect = AsyncMock(return_value=status_mock)

    await collector._save_status_data(model_mock, status_name, tar_path)

    add_to_tar_mock.assert_called_once_with(status_name, status_data, tar_path)


@pytest.mark.asyncio
async def test_fetch_juju_data(collector_config, mocker):
    """Test collection data from juju controller."""
    ts = collector.TIMESTAMP
    customer = collector_config.settings.customer
    site = collector_config.settings.site
    output_dir = collector_config.settings.collection_path
    tar_path_template = os.path.join(
        output_dir, f"{customer}_@_{site}_@_{{model}}_@_{ts}.tar"
    )
    model_uuids = {"model_1": "UUID 1", "model_2": "UUID 2"}
    models = []
    for _ in range(len(model_uuids.keys())):
        model_mock = MagicMock()
        model_mock.disconnect.side_effect = AsyncMock()
        models.append(model_mock)

    save_status_mock = mocker.patch.object(collector, "_save_status_data")
    save_bundle_mock = mocker.patch.object(collector, "_save_bundle_data")

    controller = MagicMock()
    controller.model_uuids.side_effect = AsyncMock(return_value=model_uuids)
    controller.get_model.side_effect = AsyncMock(side_effect=models)
    controller.disconnect.side_effect = AsyncMock()

    expected_status_calls = []
    expected_bundle_calls = []

    for model, model_name in zip(models, model_uuids.keys()):
        bundle_name = f"juju_bundle_@_{model_name}_@_{ts}"
        status_name = f"juju_status_@_{model_name}_@_{ts}"
        tar_path = tar_path_template.format(model=model_name)

        expected_status_calls.append(call(model, status_name, tar_path))
        expected_bundle_calls.append(call(model, bundle_name, tar_path))

    await collector.fetch_juju_data(collector_config, controller)

    save_status_mock.assert_has_calls(expected_status_calls)
    save_bundle_mock.assert_has_calls(expected_bundle_calls)

    for model in models:
        model.disconnect.assert_called_once()

    controller.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_juju_data_error(collector_config, mocker):
    """Test that `fetch_juju_data` re-raises exceptions not related to empty model.

    This function is meant to handle only JujuAPIErrors during bundle export of an empty
    model, other errors should be re-raised.
    """
    mocker.patch.object(collector, "_add_file_to_tar")
    controller = MagicMock()
    controller.disconnect.side_effect = AsyncMock()

    juju_error = defaultdict(str)
    juju_error["error"] = "Something horrible juju error occurred."

    status_mock = MagicMock()
    status_mock.to_json.return_value = "{'model': 'status}'"

    model = MagicMock()
    model.get_status.side_effect = AsyncMock(return_value=status_mock)
    model.export_bundle.side_effect = AsyncMock(
        side_effect=collector.JujuAPIError(juju_error)
    )

    controller.get_model.side_effect = AsyncMock(return_value=model)
    controller.model_uuids.side_effect = AsyncMock(
        return_value={"Broken model": "model UUID"}
    )

    with pytest.raises(collector.JujuAPIError) as exc:
        await collector.fetch_juju_data(collector_config, controller)

    assert str(exc.value) == juju_error["error"]
