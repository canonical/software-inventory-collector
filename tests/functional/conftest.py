import logging
import os
from subprocess import check_call

import pytest
import yaml

JUJU_CRED_DIR = ".local/share/juju/"
TMP_DIR = "/tmp"
SNAP_NAME = "software-inventory-collector"
SNAP_CONFIG_DIR = f"/var/snap/{SNAP_NAME}/"
CUSTOMER = "foo"
SITE = "bar"
MODEL = f"{CUSTOMER}-{SITE}"


@pytest.fixture(scope="session")
def httpserver_listen_address():
    """Create a http server at localhost on port 8675."""
    return ("127.0.0.1", 8675)


def get_juju_data():
    """Get juju account data and credentials."""
    juju_controller_file = os.path.join(os.path.expanduser("~"), JUJU_CRED_DIR, "controllers.yaml")
    juju_account_file = os.path.join(os.path.expanduser("~"), JUJU_CRED_DIR, "accounts.yaml")
    assert os.path.isfile(juju_controller_file)
    assert os.path.isfile(juju_account_file)

    with open(juju_controller_file) as controller_file:
        try:
            controller_data = yaml.safe_load(controller_file)
            current_controller = controller_data["current-controller"]
            cacert = controller_data["controllers"][current_controller]["ca-cert"]
            endpoint = controller_data["controllers"][current_controller]["api-endpoints"][0]
            assert current_controller is not None
            assert cacert is not None
            assert endpoint is not None
        except yaml.YAMLError as err:
            logging.error(err)

    with open(juju_account_file) as account_file:
        try:
            account_data = yaml.safe_load(account_file)
            user = account_data["controllers"][current_controller]["user"]
            password = account_data["controllers"][current_controller]["password"]
        except yaml.YAMLError as err:
            logging.error(err)

    return user, password, cacert, endpoint


def generate_config_data(user, password, cacert, endpoint):
    """Generate config data with the parsed juju info."""
    return {
        "juju_controller": {
            "ca_cert": cacert,
            "endpoint": endpoint,
            "password": password,
            "username": user,
        },
        "settings": {
            "collection_path": "/tmp/",
            "customer": CUSTOMER,
            "site": SITE,
        },
        "targets": [
            {
                "customer": CUSTOMER,
                "endpoint": "127.0.0.1:8675",
                "hostname": "my-foo",
                "model": MODEL,
                "site": SITE,
            }
        ],
    }


def configure_snap():
    """Configure the snap."""
    user, password, cacert, endpoint = get_juju_data()
    config_data = generate_config_data(user, password, cacert, endpoint)

    temp_config_file = os.path.join(TMP_DIR, "config.yaml")
    with open(temp_config_file, "w") as config_file:
        try:
            yaml.dump(config_data, config_file)
        except yaml.YAMLError as e:
            logging.error(e)

    snap_config_file = os.path.join(SNAP_CONFIG_DIR, "current", "config.yaml")
    assert check_call(f"sudo mv {temp_config_file} {snap_config_file}".split()) == 0  # noqa

    assert os.path.isfile(snap_config_file)


@pytest.fixture(scope="session", autouse=True)
def setup_snap():
    """Install the package to the system and cleanup afterwards.

    An environment variable TEST_SNAP is needed to install the snap.
    """
    test_snap = os.environ.get("TEST_SNAP", None)
    if test_snap:
        logging.info("Installing %s snap package...", test_snap)
        assert os.path.isfile(test_snap)
        assert check_call(f"sudo snap install --dangerous {test_snap}".split()) == 0  # noqa

        configure_snap()

    else:
        logging.error(
            "Could not find %s snap package for testing. Needs to build it first.",
            SNAP_NAME,
        )

    yield test_snap

    if test_snap:
        logging.info("Removing %s snap package...", SNAP_NAME)
        check_call(f"sudo snap remove {SNAP_NAME}".split())


@pytest.fixture(scope="session")
def http_server_response():
    """Simulate the response of the http server."""
    return {
        "dpkg": [{"package": "accountsservice", "version": "22.07.5-2ubuntu1.3"}],
        "kernel": {"kernel": "5.19.0-35-generic"},
        "snap": [
            {
                "id": "pHxyR7qwIBt0ZMMxMLbhal5V6b0cI3jE",
                "title": "CVEScan",
                "summary": "Security/CVE vulnerability monitoring for Ubuntu",
                "description": "Check whether all available security patches have been installed.",
                "installed-size": 43163648,
                "name": "cvescan",
                "publisher": {
                    "id": "canonical",
                    "username": "canonical",
                    "display-name": "Canonical",
                    "validation": "verified",
                },
                "developer": "canonical",
                "status": "active",
                "type": "app",
                "base": "core18",
                "version": "2.5.0",
                "channel": "stable",
                "tracking-channel": "latest/stable",
                "ignore-validation": False,
                "revision": "281",
                "confinement": "strict",
                "private": False,
                "devmode": False,
                "jailmode": False,
                "apps": [
                    {"snap": "cvescan", "name": "cvescan"},
                    {"snap": "cvescan", "name": "sh"},
                ],
                "license": "GPL-3.0",
                "mounted-from": "/var/lib/snapd/snaps/cvescan_281.snap",
                "links": {
                    "contact": ["https://github.com/canonical/sec-cvescan/issues"],
                    "website": ["https://github.com/canonical/sec-cvescan"],
                },
                "contact": "https://github.com/canonical/sec-cvescan/issues",
                "website": "https://github.com/canonical/sec-cvescan",
                "media": [
                    {
                        "type": "screenshot",
                        "url": "https://dashboard.snapcraft.io/appmedia/cvescan_demo.gif",
                        "width": 784,
                        "height": 688,
                    }
                ],
                "install-date": "2023-03-14T10:45:53.357333475-03:00",
            },
        ],
    }
