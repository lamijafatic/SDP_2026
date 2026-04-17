from core.ui import section, warn, info, table, bold, c, DIM, BRIGHT_CYAN, Spinner
from application.services.project_service import ProjectService
from infrastructure.persistence.toml.reader import load_config
from infrastructure.repository.smart_repo import SmartRepository
from application.services.graph_service import GraphService
from domain.resolver.sat_resolver import SATResolver


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    data = load_config()
    deps = data.get("dependencies", {})

    if not deps:
        print(warn("No dependencies to trace."))
        return 0

    section("SAT Resolution Trace")

    sp = Spinner("Building constraint graph...")
    sp.start()
    repo = SmartRepository()
    service = GraphService(repo)
    graph = service.build_graph(deps)
    sp.stop(success=True, msg="Graph built")

    print()
    print(c("  Step 1: Package Variables", bold("")))
    print(c("  ─────────────────────────────", DIM))
    for pkg_name in graph.dependencies:
        candidates = graph.get_candidates(pkg_name)
        print(c(f"  {pkg_name}:", "\033[97m") + c(f" {len(candidates)} candidate(s): " + ", ".join(str(v) for v in candidates[:5]) + ("..." if len(candidates) > 5 else ""), DIM))

    print()
    print(c("  Step 2: CNF Encoding", bold("")))
    print(c("  ─────────────────────────────", DIM))

    resolver = SATResolver(graph)
    cnf = resolver.build_cnf()
    total_clauses = len(cnf.clauses)
    total_vars = resolver.counter - 1

    rows = [
        ["Boolean variables", str(total_vars)],
        ["CNF clauses", str(total_clauses)],
        ["Packages", str(len(graph.dependencies))],
        ["Solver", "MiniSat 2.2"],
    ]
    table(["Property", "Value"], rows)

    print()
    print(c("  Step 3: Clause Types", bold("")))
    print(c("  ─────────────────────────────", DIM))
    print(info("At-least-one clauses  →  each package must have exactly one version"))
    print(info("At-most-one clauses   →  pairwise exclusion of versions"))
    print(info("Implication clauses   →  if P==v, then dep(P,v) must be satisfied"))
    print(info("Conflict clauses      →  forbidden version pairs"))
    print()
    print(c("  Step 4: Solving", bold("")))
    print(c("  ─────────────────────────────", DIM))

    sp = Spinner("Running SAT solver...")
    sp.start()
    try:
        solution = resolver.solve()
        sp.stop(success=True, msg=f"SAT solver found a satisfying assignment")
    except Exception as e:
        sp.stop(success=False, msg="UNSAT — no solution exists")
        print(c(f"  {e}", DIM))
        return 1

    print()
    print(c("  Solution:", bold("")))
    for pkg, ver in sorted(solution.items()):
        print(c(f"    {pkg}", BRIGHT_CYAN) + c(f" == {ver}", "\033[92m"))
    return 0
