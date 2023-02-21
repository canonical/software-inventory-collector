"""Module containing exceptions used by software-inventory-collector."""


class ConfigError(Exception):
    """Error occurred when reading config file."""


class ConfigMissingKeyError(ConfigError):
    """Config file is missing a required key"""

    def __init__(self, key_name: str) -> None:
        """Initiate exception instance."""
        super().__init__()
        self.key_name = key_name


class CollectionError(Exception):
    """Error occurred while collecting data from exporter."""
