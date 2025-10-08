"""No-op tracing module to replace OpenTelemetry/Phoenix without changing app logic.

Exposes Span, Tracer, Status, StatusCode, SpanKind, and factory get_tracer().
All methods are safe no-ops to preserve call sites and behavior.
"""

from contextlib import contextmanager


class StatusCode:
    OK = "OK"
    ERROR = "ERROR"


class Status:
    def __init__(self, status_code: str, description: str | None = None):
        self.status_code = status_code
        self.description = description


class SpanKind:
    INTERNAL = "INTERNAL"


class _NoopSpan:
    def __init__(self, name: str, kind: str = SpanKind.INTERNAL, attributes: dict | None = None):
        self.name = name
        self.kind = kind
        self.attributes = attributes or {}
        self.status = Status(StatusCode.OK)
        self.events = []

    # Attribute operations
    def set_attribute(self, key: str, value):
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict | None = None):
        self.events.append({"name": name, "attributes": dict(attributes or {})})

    def set_status(self, status: Status, message: str | None = None):
        # Accept either Status instance or (code, message) style used by callers
        if isinstance(status, Status):
            self.status = status
        else:
            self.status = Status(status, message)

    # Lifecycle
    def end(self):
        pass

    # Context manager protocol
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _NoopTracer:
    def start_span(self, name: str, kind: str = SpanKind.INTERNAL, attributes: dict | None = None, context=None):
        return _NoopSpan(name=name, kind=kind, attributes=attributes)

    @contextmanager
    def start_as_current_span(self, name: str, kind: str = SpanKind.INTERNAL, attributes: dict | None = None):
        span = _NoopSpan(name=name, kind=kind, attributes=attributes)
        try:
            yield span
        finally:
            pass


def get_tracer(name: str = __name__):
    return _NoopTracer()

