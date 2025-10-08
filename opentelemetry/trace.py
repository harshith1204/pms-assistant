"""No-op tracing API compatible surface.

Provides minimal objects so code can import and call tracing without effect.
"""

from contextlib import contextmanager


class _NoopStatus:
    def __init__(self, status_code=None, description: str | None = None):
        self.status_code = status_code or _NoopStatusCode.OK
        self.description = description


class _NoopStatusCode:
    OK = type("OK", (), {"name": "OK"})()
    ERROR = type("ERROR", (), {"name": "ERROR"})()


class _NoopSpanKind:
    INTERNAL = type("INTERNAL", (), {"name": "INTERNAL"})()


class _NoopSpan:
    def __init__(self, name: str = "noop_span", kind=None, attributes=None, context=None):
        self.name = name
        self.kind = kind or _NoopSpanKind.INTERNAL
        self.attributes = attributes or {}
        self.context = type("_C", (), {"trace_id": 0, "span_id": 0, "trace_state": None})()
        self.status = type("_S", (), {"status_code": _NoopStatusCode.OK, "description": ""})()
        self.events = []
        self.start_time = None
        self.end_time = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        self.events.append(type("_E", (), {"name": name, "attributes": attributes or {}, "timestamp": 0})())

    def set_status(self, status):
        self.status = status

    def end(self):
        self.end_time = 0


class _NoopTracer:
    @contextmanager
    def start_as_current_span(self, name: str, kind=None, attributes=None):
        span = _NoopSpan(name=name, kind=kind, attributes=attributes)
        yield span

    def start_span(self, name: str, kind=None, attributes=None, context=None):
        return _NoopSpan(name=name, kind=kind, attributes=attributes, context=context)


_GLOBAL_TRACER = _NoopTracer()


def get_tracer(name: str):
    return _GLOBAL_TRACER


def set_tracer_provider(provider):
    # no-op
    return None


# Re-exported names for compatibility
Status = _NoopStatus
StatusCode = _NoopStatusCode
SpanKind = _NoopSpanKind

