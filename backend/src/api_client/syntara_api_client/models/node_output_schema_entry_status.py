from enum import Enum


class NodeOutputSchemaEntryStatus(str, Enum):
    AVAILABLE = "available"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"

    def __str__(self) -> str:
        return str(self.value)
