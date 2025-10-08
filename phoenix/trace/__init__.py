"""No-op Phoenix trace helpers."""

class using_project:
    def __init__(self, project_name: str):
        self.project_name = project_name

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False

