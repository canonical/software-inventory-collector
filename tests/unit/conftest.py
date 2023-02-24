"""Fixtures for software_inventory_collector unit tests."""
import pytest

from software_inventory_collector.config import (
    Config,
    _ConfigJujuController,
    _ConfigSettings,
    _ConfigTarget,
)


@pytest.fixture()
def collector_config_data() -> dict:
    """Dictionary that can be used to initialize working Config object.

    Use class method Config.from_dict() to create instance using this data.
    """
    site = "Unit tests"
    customer = "Unit testing customer"
    return {
        "settings": {
            "collection_path": "/path/to/output/",
            "customer": customer,
            "site": site,
        },
        "juju_controller": {
            "endpoint": "10.0.0.1:17070",
            "username": "admin",
            "password": "admin",
            "ca_cert": "--start cert--\ncert data\n--end cert--",
        },
        "targets": [
            {
                "endpoint": "10.10.10.1:8675",
                "hostname": "exporter-1",
                "model": "openstack",
                "site": site,
                "customer": customer,
            },
            {
                "endpoint": "10.20.20.1:8675",
                "hostname": "exporter-2",
                "model": "k8s",
                "site": site,
                "customer": customer,
            },
        ],
    }


@pytest.fixture()
def collector_config() -> Config:
    """Fully populated config object."""
    customer = "Unit testing Customer"
    site = "Unit tests"
    general_settings = _ConfigSettings(
        collection_path="/path/to/output",
        customer=customer,
        site=site,
    )
    juju_settings = _ConfigJujuController(
        endpoint="10.0.0.1:17070",
        ca_cert="--start cert--\ncert data\n--end cert--",
        username="admin",
        password="admin",
    )
    targets = [
        _ConfigTarget(
            endpoint="10.10.10.1:8765",
            hostname="exporter-host-1",
            model="model 1",
            customer=customer,
            site=site,
        ),
        _ConfigTarget(
            endpoint="10.10.10.2:8765",
            hostname="exporter-host-2",
            model="model 2",
            customer=customer,
            site=site,
        ),
    ]
    return Config(
        settings=general_settings, juju_controller=juju_settings, targets=targets
    )
