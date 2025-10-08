"""No-op Phoenix TraceDataset shim."""

class TraceDataset:
    def __init__(self, dataframe=None, name: str | None = None):
        self.dataframe = dataframe
        self.name = name

