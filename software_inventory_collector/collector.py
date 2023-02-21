"""Implementation of collector functions from various data sources."""
import datetime
import json
import os
import tarfile
from tempfile import NamedTemporaryFile

import requests
import yaml
from juju.controller import Controller
from juju.errors import JujuAPIError

from software_inventory_collector.config import Config
from software_inventory_collector.exception import CollectionError

ENDPOINTS = ["dpkg", "snap", "kernel"]

TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def _add_file_to_tar(file_name: str, content: str, tar_path: str) -> None:
    """Write content to a file with specified name and add it to tarball.

    :param file_name: Resulting name of the file in tarball
    :param content: Content of the file
    :param tar_path: path to tarball to which the file will be added.
    :return: None
    """
    with NamedTemporaryFile() as temp_file:
        temp_file.write(content.encode("UTF-8"))
        temp_file.flush()
        with tarfile.open(tar_path, "a", encoding="UTF-8") as tar_file:
            tar_file.add(temp_file.name, arcname=file_name)


def get_exporter_data(config: Config) -> None:
    """Query exporter endpoints and collect data."""
    for target in config.targets:
        url = f"http://{target.endpoint}/"
        tar = f"{target.customer}_@_{target.site}_@_{target.model}_@_{TIMESTAMP}.tar"
        tar_path = os.path.join(config.settings.collection_path, tar)
        for endpoint in ENDPOINTS:
            try:
                content = requests.get(url + endpoint, timeout=60)
                content.raise_for_status()
            except requests.exceptions.RequestException as exc:
                raise CollectionError(
                    f"Failed to collect data from target '{target.endpoint}': f{exc}"
                ) from exc

            file_name = f"{endpoint}_@_{target.hostname}_@_{TIMESTAMP}"
            _add_file_to_tar(file_name, content.text, tar_path)


async def get_controller(config: Config) -> Controller:
    """Return connected instance of Juju Controller."""
    controller = Controller()
    await controller.connect(
        endpoint=config.juju_controller.endpoint,
        username=config.juju_controller.username,
        password=config.juju_controller.password,
        cacert=config.juju_controller.ca_cert,
    )
    return controller


async def get_juju_data(config: Config, controller: Controller) -> None:
    """Query Juju controller and collect information about models."""
    model_uuids = await controller.model_uuids()

    for model_name in model_uuids.keys():
        model = await controller.get_model(model_name)
        status = await model.get_status()
        try:
            bundle = await model.export_bundle()
        except JujuAPIError as exc:
            if str(exc) == "nothing to export as there are no applications":
                bundle = "{}"
            else:
                raise exc
        await model.disconnect()

        status_file = f"juju_status_@_{model_name}_@_{TIMESTAMP}"
        bundle_file = f"juju_bundle_@_{model_name}_@_{TIMESTAMP}"
        tar = (
            f"{config.settings.customer}_@_{config.settings.site}_@_{model_name}_"
            f"@_{TIMESTAMP}.tar"
        )
        tar_path = os.path.join(
            config.settings.collection_path,
            tar,
        )

        _add_file_to_tar(status_file, status.to_json(), tar_path)

        bundle_yaml = yaml.load_all(bundle, Loader=yaml.FullLoader)
        for data in bundle_yaml:
            bundle_json = json.dumps(data)
            # skip SAAS; multiple documents, we need to import only the bundle
            if "offers" in bundle_json:
                continue

            _add_file_to_tar(bundle_file, bundle_json, tar_path)

    await controller.disconnect()
