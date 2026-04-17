from pysat.formula import CNF
from pysat.solvers import Solver
from domain.resolver.base_resolver import BaseResolver
from domain.exceptions.resolution_error import ResolutionError


class SATResolver(BaseResolver):
    def __init__(self, graph):
        super().__init__(graph)
        self.repo = graph.repo
        self.var_map = {}
        self.reverse_map = {}
        self.counter = 1

    def _get_var(self, package, version):
        key = (package, str(version))
        if key not in self.var_map:
            self.var_map[key] = self.counter
            self.reverse_map[self.counter] = key
            self.counter += 1
        return self.var_map[key]

    def build_cnf(self):
        cnf = CNF()

        # Pre-check: raise early if any direct dep has no candidates
        self.validate_graph()

        # Phase 1: exactly-one constraint per package
        for pkg in self.graph.dependencies:
            candidates = self.graph.get_candidates(pkg)
            if not candidates:
                # Force UNSAT for this package
                cnf.append([])
                continue
            vars_ = [self._get_var(pkg, v) for v in candidates]
            # At least one version must be selected
            cnf.append(vars_)
            # At most one version (pairwise exclusion)
            for i in range(len(vars_)):
                for j in range(i + 1, len(vars_)):
                    cnf.append([-vars_[i], -vars_[j]])

        # Phase 2: implication clauses (if P==v selected, dep must be satisfied)
        for pkg in self.graph.dependencies:
            candidates = self.graph.get_candidates(pkg)
            for v in candidates:
                var_p = self._get_var(pkg, v)
                deps = self.graph.get_dependencies(pkg, v)
                for dep_name, constraint in deps:
                    dep_candidates = self.graph.get_candidates(dep_name)
                    valid = [
                        self._get_var(dep_name, dv)
                        for dv in dep_candidates
                        if constraint.is_satisfied_by(dv)
                    ]
                    if valid:
                        # ¬p ∨ (d1 ∨ d2 ∨ ...)
                        cnf.append([-var_p] + valid)
                    else:
                        # No valid dep version exists → forbid selecting this parent version
                        cnf.append([-var_p])

        # Phase 3: explicit conflict clauses from repo
        conflicts = self.repo.get_conflicts()
        for conflict in conflicts:
            p1_str, p2_str = conflict
            pkg1, ver1 = p1_str.split("@")
            pkg2, ver2 = p2_str.split("@")
            # Only add clause if both are in our graph
            if pkg1 in self.graph.dependencies and pkg2 in self.graph.dependencies:
                v1_key = (pkg1, ver1)
                v2_key = (pkg2, ver2)
                if v1_key in self.var_map or True:
                    v1 = self._get_var(pkg1, ver1)
                    v2 = self._get_var(pkg2, ver2)
                    cnf.append([-v1, -v2])

        return cnf

    def solve(self):
        cnf = self.build_cnf()

        with Solver(name="minisat22", bootstrap_with=cnf) as solver:
            if not solver.solve():
                raise ResolutionError(
                    "No solution found. The combined constraints are unsatisfiable.\n"
                    "Try relaxing version constraints or check for conflicting packages."
                )
            model = solver.get_model()

        solution = {}
        for val in model:
            if val > 0 and val in self.reverse_map:
                pkg, ver = self.reverse_map[val]
                if pkg in self.graph.dependencies:
                    solution[pkg] = ver

        return self._prefer_latest(solution)

    def _prefer_latest(self, solution: dict) -> dict:
        """Greedily upgrade packages to latest compatible versions (multi-pass until stable)."""
        improved = dict(solution)
        changed = True
        while changed:
            changed = False
            for pkg in list(improved.keys()):
                candidates = sorted(
                    self.graph.get_candidates(pkg),
                    key=lambda v: v.to_tuple(),
                    reverse=True,
                )
                for candidate in candidates:
                    c_str = str(candidate)
                    if c_str == improved[pkg]:
                        break
                    if self._is_upgrade_valid(pkg, c_str, improved):
                        if c_str != improved[pkg]:
                            improved[pkg] = c_str
                            changed = True
                        break
        return improved

    def _is_upgrade_valid(self, pkg: str, new_ver: str, solution: dict) -> bool:
        """Check if upgrading pkg to new_ver still satisfies all inter-package constraints."""
        test_sol = dict(solution)
        test_sol[pkg] = new_ver

        from domain.models.version import Version
        new_v = Version(new_ver)

        # Check that new_ver satisfies constraints imposed by other packages that depend on pkg
        for other_pkg, other_ver in test_sol.items():
            if other_pkg == pkg:
                continue
            other_ver_obj = Version(other_ver)
            deps = self.graph.get_dependencies(other_pkg, other_ver_obj)
            for dep_name, constraint in deps:
                if dep_name == pkg:
                    if not constraint.is_satisfied_by(new_v):
                        return False

        # Check that new_ver's own deps are still satisfiable with current solution
        new_v_obj = Version(new_ver)
        deps = self.graph.get_dependencies(pkg, new_v_obj)
        for dep_name, constraint in deps:
            if dep_name in test_sol:
                from domain.models.version import Version as V
                if not constraint.is_satisfied_by(V(test_sol[dep_name])):
                    return False

        return True
