"""No-op SDK shim."""

class TracerProvider:
    def __init__(self, *args, **kwargs):
        pass

    def add_span_processor(self, processor):
        pass

    def shutdown(self):
        pass

