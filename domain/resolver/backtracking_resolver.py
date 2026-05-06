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
        from domain.models.version import Version as _Version
        ver_obj = version if isinstance(version, _Version) else _Version(str(version))
        version_str = str(version)

        # 1. Explicit conflicts from repo
        if hasattr(self.graph, "repo"):
            conflicts = self.graph.repo.get_conflicts()
            for p1, p2 in conflicts:
                cp1, cv1 = p1.split("@")
                cp2, cv2 = p2.split("@")
                sel = self.solution
                if pkg == cp1 and version_str == cv1 and cp2 in sel and str(sel[cp2]) == cv2:
                    return False
                if pkg == cp2 and version_str == cv2 and cp1 in sel and str(sel[cp1]) == cv1:
                    return False

        # 2. Backward: constraints already-assigned packages impose ON this package
        for sel_name, sel_ver in self.solution.items():
            for dep_name, constraint in self.graph.get_dependencies(sel_name, sel_ver):
                if dep_name == pkg and not constraint.is_satisfied_by(ver_obj):
                    return False

        # 3. Forward: constraints this package imposes ON others
        for dep_name, constraint in self.graph.get_dependencies(pkg, version):
            if dep_name in self.solution:
                if not constraint.is_satisfied_by(self.solution[dep_name]):
                    return False
            else:
                candidates = self.graph.get_candidates(dep_name)
                if not any(constraint.is_satisfied_by(v) for v in candidates):
                    return False
        return True
