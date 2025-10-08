"""No-op OpenTelemetry shim to disable tracing while preserving interfaces."""

from . import trace  # re-export for `from opentelemetry import trace`

__all__ = ["trace"]

