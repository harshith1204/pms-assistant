"""No-op exporters and processors."""

class SpanProcessor:
    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        pass

    def shutdown(self, timeout_millis=30000):
        pass

    def force_flush(self, timeout_millis=30000):
        pass


class SpanExporter:
    def export(self, spans):
        return None


class ConsoleSpanExporter:
    def export(self, spans):
        return None


class BatchSpanProcessor(SpanProcessor):
    def __init__(self, exporter):
        self.exporter = exporter

