from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.toml.writer import save_config
from infrastructure.repository.smart_repo import SmartRepository


class DependencyService:
    def __init__(self, repo=None):
        self.repo = repo or SmartRepository()

    def add(self, name: str, constraint: str):
        data = load_config()
        data.setdefault("dependencies", {})[name] = constraint
        save_config(data)

    def remove(self, name: str):
        data = load_config()
        deps = data.get("dependencies", {})
        if name not in deps:
            raise KeyError(f"Package '{name}' is not in dependencies")
        del deps[name]
        save_config(data)

    def update_constraint(self, name: str, new_constraint: str):
        data = load_config()
        deps = data.get("dependencies", {})
        if name not in deps:
            raise KeyError(f"Package '{name}' is not in dependencies")
        deps[name] = new_constraint
        save_config(data)

    def list_direct(self) -> dict:
        data = load_config()
        return data.get("dependencies", {})

    def get_available_versions(self, name: str) -> list:
        versions = self.repo.get_versions(name)
        return sorted(versions, key=lambda v: tuple(int(x) for x in v.split(".")))

    def search(self, query: str) -> list:
        query = query.lower()
        local_pkgs = self.repo.list_packages()
        matches = [p for p in local_pkgs if query in p.lower()]
        # Also try exact PyPI lookup if not already matched
        if hasattr(self.repo, 'package_exists') and query not in [m.lower() for m in matches]:
            if self.repo.package_exists(query):
                matches.append(query)
        return matches
