from infrastructure.repository.abstract_repo import AbstractRepository
from infrastructure.repository.local_repo import LocalRepository
from infrastructure.repository.pypi_repo import PyPIRepository


class SmartRepository(AbstractRepository):
    """
    Tries the local demo registry first.
    Falls back to live PyPI for any package not found locally.
    Conflicts come only from the local registry.
    """

    def __init__(self):
        self._local = LocalRepository()
        self._pypi = PyPIRepository()
        self._local_packages = set(
            k for k in self._local.data.keys() if k != "conflicts"
        )

    def _use_pypi(self, package_name: str) -> bool:
        return package_name not in self._local_packages

    def get_versions(self, package_name: str) -> list:
        if self._use_pypi(package_name):
            return self._pypi.get_versions(package_name)
        return self._local.get_versions(package_name)

    def get_dependencies(self, package_name: str, version: str) -> list:
        if self._use_pypi(package_name):
            return self._pypi.get_dependencies(package_name, version)
        return self._local.get_dependencies(package_name, version)

    def get_conflicts(self) -> list:
        return self._local.get_conflicts()

    def list_packages(self) -> list:
        return sorted(self._local_packages)

    def package_exists(self, name: str) -> bool:
        if name in self._local_packages:
            return True
        return self._pypi.package_exists(name)
