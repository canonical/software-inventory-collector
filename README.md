# Software Inventory Collector

CLI tool for collecting data exported by
[Software Inventory Exporter](https://snapcraft.io/software-inventory-exporter)
. Collected data is mostly related to software packages installed on the system
and it currently contains:

* `.deb` packages installed on machines that run the exporter
* `snap` packages installed on machines that run the exporter
* Kernel version on machines that run the exporter
* Status of juju models deployed by configured Juju controller
* Exported bundles of juju models deployed by configured Juju controller

## Installation

While this application can be installed in standalone mode either as python
package or a `snap`, it is intended to be deployed by a
[Juju charm](https://charmhub.io/software-inventory-collector) that properly
configures it.

## Configuration

Below is a brief explanation of minimum viable configuration required
by `software-inventory-collector`

```yaml
juju_controller:  # Configuration related to Juju controller
  ca_cert: |  # CA certificate used by Juju controller (in .pem format)
    -----BEGIN CERTIFICATE-----
    <Certificate data>
    -----END CERTIFICATE-----
  endpoint: 10.0.0.1:17070  # IP (or hostname) and port of a Juju controller
  username: admin  # Username used to log into the Juju controller
  password: password  # Password used to log into the juju controller
settings:  # General settings
  collection_path: /path/to/output  # Path where collected data will be
                                    # stored (must be writable directory
                                    # by the process)
  customer: Customer 1  # Arbitrary name for the customer that owns the cloud
  site: cloud 1  # Arbitrary name identifying site/deployment
targets:  # List of Software Inventory Exporters
- customer: Customer 1  # Arbitrary name identifying site/deployment
  endpoint: 10.10.10.5:8675  # IP (or hostname) and port of an exporter
  hostname: juju-e1efe1-pacakge-exporter-2  # hostname assigned to the exporter by juju
  model: package-exporter  # Name of the Juju model in which the exporter is deployed
  site: cloud 1  # Arbitrary name identifying site/deployment
```
