import time
from infrastructure.repository.smart_repo import SmartRepository
from application.services.graph_service import GraphService
from domain.resolver.sat_resolver import SATResolver
from domain.resolver.backtracking_resolver import BacktrackingResolver
from domain.resolver.hypergraph_resolver import HypergraphResolver
from application.dto.resolution_result import ResolutionResult


class ResolutionService:
    def __init__(self, repo=None):
        self.repo = repo or SmartRepository()

    def resolve(self, dependencies: dict, strategy="sat") -> ResolutionResult:
        graph_svc = GraphService(self.repo)
        graph = graph_svc.build_graph(dependencies)

        start = time.time()

        if strategy == "backtracking":
            resolver = BacktrackingResolver(graph)
        elif strategy == "hypergraph":
            resolver = HypergraphResolver(graph)
        else:
            resolver = SATResolver(graph)

        solution = resolver.solve()
        elapsed = (time.time() - start) * 1000

        result = ResolutionResult(
            solution=solution,
            strategy=strategy,
            elapsed_ms=elapsed,
        )

        if hasattr(resolver, "cnf_clauses"):
            result.clause_count = resolver.cnf_clauses

        return result

    def explain(self, dependencies: dict) -> list:
        graph_svc = GraphService(self.repo)
        graph = graph_svc.build_graph(dependencies)
        resolver = SATResolver(graph)

        try:
            solution = resolver.solve()
        except Exception as e:
            return [f"Resolution failed: {e}"]

        lines = []
        for pkg, ver in solution.items():
            dep = graph.dependencies.get(pkg)
            constraint_str = str(dep.constraint) if dep else "any"
            subdeps = graph.get_dependencies(pkg, ver)
            reason_parts = [f"satisfies constraint {constraint_str}"]
            for dep_name, dep_constraint in subdeps:
                if dep_name in solution:
                    reason_parts.append(
                        f"requires {dep_name}{dep_constraint} → {solution[dep_name]}"
                    )
            lines.append((pkg, ver, "; ".join(reason_parts)))

        return lines

    def detect_conflicts(self) -> list:
        conflicts = self.repo.get_conflicts()
        result = []
        for c in conflicts:
            p1, p2 = c
            pkg1, ver1 = p1.split("@")
            pkg2, ver2 = p2.split("@")
            result.append({
                "package1": pkg1,
                "version1": ver1,
                "package2": pkg2,
                "version2": ver2,
            })
        return result
