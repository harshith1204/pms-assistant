"""No-op OTLP HTTP span exporter shim."""

class OTLPSpanExporter:
    def __init__(self, *args, **kwargs):
        pass

    def export(self, spans):
        return None

