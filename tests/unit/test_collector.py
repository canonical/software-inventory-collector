"""Tests for software_inventory_collector.collector module"""
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


def test_get_exporter_data_success(collector_config, mocker):
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

    collector.get_exporter_data(collector_config)

    get_mock.assert_has_calls(expected_requests)
    add_tar_mock.assert_has_calls(expected_tar_calls)


def test_get_exporter_data_error(collector_config, mocker):
    """Test handling of error during collection of data from exporter endpoint."""
    exception = collector.requests.RequestException

    mocker.patch.object(collector.requests, "get", side_effect=exception)
    add_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")

    with pytest.raises(collector.CollectionError):
        collector.get_exporter_data(collector_config)

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


@pytest.mark.asyncio
async def test_get_juju_data(collector_config, mocker):
    """Test collection data from juju controller.

    Note (mkalcok): This is absolutely monstrous unit tests that shouldn't exist but
    there's just too much that needs to be mocked and prepared in terms of data and
    structures that it ended up as a huge UT. I'll try to go briefly over its steps:
      * Prepare some commonly used variables
      * Patch Controller object and function that creates tarballs
      * Prepare data about juju models and setup expected calls to `_add_file_to_tar`
        - Setup regular model called "basic"
        - Setup empty model that'd trigger `JujuAPIError` because there are no
          applications to export.
        - Setup model with Cross Model Relation to make sure that we ignore CMR data in
          bundle export.
      * Once all is prepared, run `get_juju_data` function.
      * Verify that expected calls were made.
    """
    ts = collector.TIMESTAMP
    site = collector_config.settings.site
    customer = collector_config.settings.customer
    output_dir = collector_config.settings.collection_path

    add_file_to_tar_mock = mocker.patch.object(collector, "_add_file_to_tar")
    tar_calls = []
    controller = MagicMock()
    controller.disconnect.side_effect = AsyncMock()

    # Prepare data for basic model
    bundle_basic = '{"bundle": "basic"}'
    status_basic = MagicMock()
    status_basic.to_json.return_value = "{'status': 'basic'}"
    model_basic = MagicMock()
    model_basic.name = "Basic model"
    model_basic.uuid = "Basic UUID"
    model_basic.export_bundle.side_effect = AsyncMock(return_value=bundle_basic)
    model_basic.get_status.side_effect = AsyncMock(return_value=status_basic)
    model_basic.disconnect.side_effect = AsyncMock()
    # expected data exports for basic model
    basic_model_tar = f"{output_dir}/{customer}_@_{site}_@_{model_basic.name}_@_{ts}.tar"
    tar_calls.append(
        call(
            f"juju_status_@_{model_basic.name}_@_{ts}",
            status_basic.to_json.return_value,
            basic_model_tar,
        )
    )
    tar_calls.append(
        call(
            f"juju_bundle_@_{model_basic.name}_@_{ts}",
            bundle_basic,
            basic_model_tar,
        )
    )

    # Prepare data for empty model
    juju_err = defaultdict(str)
    juju_err["error"] = "nothing to export as there are no applications"
    empty_model_err = collector.JujuAPIError(juju_err)
    status_empty = MagicMock()
    status_empty.to_json.return_value = "{'status': 'empty'}"
    model_empty = MagicMock()
    model_empty.name = "Empty model"
    model_empty.uuid = "Empty uuid"
    model_empty.export_bundle.side_effect = AsyncMock(side_effect=empty_model_err)
    model_empty.get_status.side_effect = AsyncMock(return_value=status_empty)
    model_empty.disconnect.side_effect = AsyncMock()
    # expected data exports for empty model
    empty_model_tar = f"{output_dir}/{customer}_@_{site}_@_{model_empty.name}_@_{ts}.tar"
    tar_calls.append(
        call(
            f"juju_status_@_{model_empty.name}_@_{ts}",
            status_empty.to_json.return_value,
            empty_model_tar,
        )
    )
    tar_calls.append(
        call(
            f"juju_bundle_@_{model_empty.name}_@_{ts}",
            "{}",
            empty_model_tar,
        )
    )

    # Prepare data for model with CMR
    status_cmr = MagicMock()
    status_cmr.to_json.return_value = "{'status': 'cmr'}"
    model_cmr = MagicMock()
    model_cmr.name = "CMR model"
    model_cmr.uuid = "CMR uuid"
    model_cmr.export_bundle.side_effect = AsyncMock(
        return_value="bundle: cmr\n---\noffers: cmr offers"
    )
    model_cmr.get_status.side_effect = AsyncMock(return_value=status_cmr)
    model_cmr.disconnect.side_effect = AsyncMock()
    # expected data exports for model with CMR
    cmr_model_tar = f"{output_dir}/{customer}_@_{site}_@_{model_cmr.name}_@_{ts}.tar"
    tar_calls.append(
        call(
            f"juju_status_@_{model_cmr.name}_@_{ts}",
            status_cmr.to_json.return_value,
            cmr_model_tar,
        )
    )
    tar_calls.append(
        call(
            f"juju_bundle_@_{model_cmr.name}_@_{ts}",
            '{"bundle": "cmr"}',
            cmr_model_tar,
        )
    )

    # mock controller methods
    models = [model_basic, model_empty, model_cmr]
    model_uuids = {model.name: model.uuid for model in models}

    controller.model_uuids.side_effect = AsyncMock(return_value=model_uuids)
    controller.get_model.side_effect = AsyncMock(side_effect=models)

    # collect data from juju
    await collector.get_juju_data(collector_config, controller)

    # check expected calls
    add_file_to_tar_mock.assert_has_calls(tar_calls)
    controller.disconnect.assert_called_once()
    for model in models:
        model.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_get_juju_data_error(collector_config, mocker):
    """Test that `get_juju_data` re-raises exceptions not related to empty model.

    This function is meant to handle only JujuAPIErrors during bundle export of an empty
    model, other errors should be re-raised.
    """
    controller = MagicMock()
    controller.disconnect.side_effect = AsyncMock()

    juju_error = defaultdict(str)
    juju_error["error"] = "Something horrible juju error occurred."

    model = MagicMock()
    model.get_status.side_effect = AsyncMock(return_value="Model status")
    model.export_bundle.side_effect = AsyncMock(
        side_effect=collector.JujuAPIError(juju_error)
    )

    controller.get_model.side_effect = AsyncMock(return_value=model)
    controller.model_uuids.side_effect = AsyncMock(
        return_value={"Broken model": "model UUID"}
    )

    with pytest.raises(collector.JujuAPIError) as exc:
        await collector.get_juju_data(collector_config, controller)

    assert str(exc.value) == juju_error["error"]
