from abc import ABC, abstractmethod


class AbstractRepository(ABC):
    @abstractmethod
    def get_versions(self, package_name: str) -> list:
        """Return list of available version strings."""
        ...

    @abstractmethod
    def get_dependencies(self, package_name: str, version: str) -> list:
        """Return list of dependency strings like ['numpy>=1.20']."""
        ...

    @abstractmethod
    def get_conflicts(self) -> list:
        """Return list of conflict pairs like [['pkg1@v1', 'pkg2@v2']]."""
        ...

    def list_packages(self) -> list:
        """Return names of all known packages."""
        return []
