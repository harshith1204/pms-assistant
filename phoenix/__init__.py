"""No-op Phoenix shim."""

class Client:
    def __init__(self, *args, **kwargs):
        pass

    def trace(self, name: str, span_kind: str = "INTERNAL"):
        class _Ctx:
            def __enter__(self_inner):
                return None
            def __exit__(self_inner, exc_type, exc, tb):
                return False
        return _Ctx()

