from abc import ABC, abstractmethod


class BaseResolver(ABC):
    def __init__(self, graph):
        self.graph = graph

    @abstractmethod
    def solve(self) -> dict:
        """Return {package_name: version_str} mapping."""
        ...

    def validate_graph(self):
        empty = [
            pkg for pkg in self.graph.dependencies
            if not self.graph.get_candidates(pkg)
        ]
        if empty:
            from domain.exceptions.resolution_error import ResolutionError
            raise ResolutionError(
                "No valid candidates found for some packages.",
                unsatisfied=empty
            )
