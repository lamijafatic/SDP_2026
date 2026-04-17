import json
import os

from infrastructure.repository.abstract_repo import AbstractRepository


def _find_repo_json():
    """Locate data/repository.json whether running from source or installed."""
    # 1. Current working directory (project root when running from source)
    cwd_path = os.path.join(os.getcwd(), "data", "repository.json")
    if os.path.exists(cwd_path):
        return cwd_path

    # 2. Relative to this file (works in development: infrastructure/repository/ → ../../data/)
    here = os.path.dirname(os.path.abspath(__file__))
    rel_path = os.path.normpath(os.path.join(here, "..", "..", "data", "repository.json"))
    if os.path.exists(rel_path):
        return rel_path

    # 3. Installed package data via importlib.resources (Python 3.9+)
    try:
        import importlib.resources as ir
        ref = ir.files("data").joinpath("repository.json")
        if ref.is_file():
            return str(ref)
    except Exception:
        pass

    raise FileNotFoundError(
        "Cannot find data/repository.json. "
        "Make sure you are running arbor from the project directory or have installed it correctly."
    )


class LocalRepository(AbstractRepository):
    def __init__(self):
        path = _find_repo_json()
        with open(path) as f:
            self.data = json.load(f)

    def get_versions(self, package_name: str) -> list:
        return list(self.data.get(package_name, {}).keys())

    def get_dependencies(self, package_name: str, version: str) -> list:
        return self.data.get(package_name, {}).get(version, [])

    def get_conflicts(self) -> list:
        return self.data.get("conflicts", [])

    def list_packages(self) -> list:
        return [k for k in self.data.keys() if k != "conflicts"]
