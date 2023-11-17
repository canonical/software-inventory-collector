"""Set up software_inventory_collector python module cli scripts."""

from setuptools import setup

with open("README.md", encoding="utf-8") as f:
    readme = f.read()

with open("LICENSE", encoding="utf-8") as f:
    project_license = f.read()

setup(
    name="software_inventory_collector",
    use_scm_version={"local_scheme": "node-and-date"},
    description="Client for collecting data from charm-inventory-exporter",
    long_description=readme,
    author="Canonical BootStack",
    url="https://github.com/canonical/software-inventory-collector",
    license=project_license,
    packages=["software_inventory_collector"],
    entry_points={
        "console_scripts": [
            "software-inventory-collector=software_inventory_collector.cli:main",
        ]
    },
    setup_requires=["setuptools_scm"],
)
