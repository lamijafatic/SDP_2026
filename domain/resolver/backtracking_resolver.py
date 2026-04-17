from domain.resolver.base_resolver import BaseResolver
from domain.exceptions.resolution_error import ResolutionError


class BacktrackingResolver(BaseResolver):
    def __init__(self, graph):
        super().__init__(graph)
        self.solution = {}

    def solve(self):
        self.validate_graph()
        self.solution = {}
        packages = list(self.graph.dependencies.keys())
        if not self._backtrack(packages, 0):
            raise ResolutionError(
                "No solution found via backtracking. Constraints may be unsatisfiable."
            )
        return {pkg: str(ver) for pkg, ver in self.solution.items()}

    def _backtrack(self, packages, index):
        if index == len(packages):
            return True
        pkg = packages[index]
        candidates = self.graph.get_candidates(pkg)
        # Try newest versions first (better UX)
        for version in reversed(candidates):
            if self._is_valid(pkg, version):
                self.solution[pkg] = version
                if self._backtrack(packages, index + 1):
                    return True
                del self.solution[pkg]
        return False

    def _is_valid(self, pkg, version):
        # Check explicit conflicts from repo
        if hasattr(self.graph, "repo"):
            conflicts = self.graph.repo.get_conflicts()
            for c in conflicts:
                p1, p2 = c
                cp1, cv1 = p1.split("@")
                cp2, cv2 = p2.split("@")
                sel = self.solution
                if pkg == cp1 and str(version) == cv1 and cp2 in sel and str(sel[cp2]) == cv2:
                    return False
                if pkg == cp2 and str(version) == cv2 and cp1 in sel and str(sel[cp1]) == cv1:
                    return False

        # Check dependency constraints against current solution
        deps = self.graph.get_dependencies(pkg, version)
        for dep_name, constraint in deps:
            if dep_name in self.solution:
                if not constraint.is_satisfied_by(self.solution[dep_name]):
                    return False
            else:
                candidates = self.graph.get_candidates(dep_name)
                if not any(constraint.is_satisfied_by(v) for v in candidates):
                    return False
        return True
