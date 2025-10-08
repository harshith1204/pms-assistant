"""No-op OpenTelemetry resources shim."""

class Resource:
    def __init__(self, attributes=None):
        self.attributes = attributes or {}

    @classmethod
    def create(cls, attributes):
        return cls(attributes)

