class ConfigError(Exception):
    """Raised when there is an error with the configuration file."""


class NotFoundAgainError(Exception):
    """Raised when an entity is not found again."""

    def __init__(self, entity_id: str):
        super().__init__(f"Entity not found: {entity_id}")


class ServiceTimeoutError(Exception):
    """Raised when a service call was not successful due to recently being called."""