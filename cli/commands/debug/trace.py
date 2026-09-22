"""
vertex trace, step-by-step trace of the hypergraph resolution process
on the current project's actual dependencies.
"""
from core.ui import (
    section, ok, warn, info, bold, c, DIM,
    BRIGHT_GREEN, BRIGHT_CYAN, BRIGHT_YELLOW, BRIGHT_WHITE, BOLD,
    table, Spinner,
)
from application.services.project_service import ProjectService
from infrastructure.persistence.toml.reader import load_config
from infrastructure.repository.smart_repo import SmartRepository
from application.services.graph_service import GraphService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'vertex init' first."))
        return 1

    data = load_config()
    deps = data.get("dependencies", {})
    if not deps:
        print(warn("No dependencies to trace. Use 'vertex add' to add packages."))
        return 0

    section("Hypergraph Resolution Trace")
    print(c(f"  Project has {len(deps)} direct dependencies.\n", DIM))

    # ── Step 1: Build graph ───────────────────────────────────────────────────
    print(c("  Step 1, Build dependency graph\n", BOLD, BRIGHT_WHITE))
    sp = Spinner("Fetching versions and building constraint graph...")
    sp.start()
    repo  = SmartRepository()
    gsvc  = GraphService(repo)
    graph = gsvc.build_graph(deps)
    sp.stop(success=True, msg=f"Graph built, {len(graph.dependencies)} packages, "
            f"{sum(len(graph.get_candidates(p)) for p in graph.dependencies)} total candidates")

    print()
    for pkg in sorted(graph.dependencies.keys()):
        cands = graph.get_candidates(pkg)
        c_str = ", ".join(str(v) for v in cands[:5])
        more  = f"  ... +{len(cands)-5} more" if len(cands) > 5 else ""
        print(f"  {c(pkg, BRIGHT_WHITE):<28} {c(len(cands), BRIGHT_CYAN)} versions:  "
              f"{c(c_str, DIM)}{c(more, DIM)}")

    # ── Step 2: Build hypergraph ──────────────────────────────────────────────
    print()
    print(c("  Step 2, Build hypergraph  H = (V, E)\n", BOLD, BRIGHT_WHITE))
    from model_math_trans import build_hypergraph, compute_role_classes, build_role_graph
    sp = Spinner("Building hypergraph...")
    sp.start()
    H         = build_hypergraph(graph, repo)
    dep_edges = [e for e in H.E if e.label == "dep"]
    sp.stop(success=True, msg=f"|V| = {len(H.V)} nodes  |  |E| = {len(dep_edges)} dep hyperedges")

    # ── Step 3: Role class decomposition ─────────────────────────────────────
    print()
    print(c("  Step 3, Role class decomposition\n", BOLD, BRIGHT_WHITE))
    sp = Spinner("Computing role classes...")
    sp.start()
    roles               = compute_role_classes(H)
    role_deps, role_cfl = build_role_graph(H, roles)
    sp.stop(success=True, msg=f"{len(H.V)} version nodes  →  {len(roles)} role classes")

    k         = len(roles)
    total_v   = len(H.V)
    reduction = round((1 - k / total_v) * 100) if total_v else 0
    print()
    print(c(f"  Reduction: {total_v} variables  →  {k} role class variables  "
            f"({reduction}% compression)\n", DIM))

    # Show top packages by role class count
    from collections import Counter
    rc_by_pkg = Counter(rc.pkg_name for rc in roles)
    rows = []
    for pkg, n_rc in sorted(rc_by_pkg.items(), key=lambda x: -x[1])[:10]:
        n_cands = len(graph.get_candidates(pkg))
        rows.append([pkg, str(n_cands), str(n_rc)])
    if rows:
        table(["Package", "Versions", "Role classes"], rows)

    # ── Step 4: Phase A SAT ───────────────────────────────────────────────────
    print()
    print(c("  Step 4, Phase A: SAT skeleton resolution\n", BOLD, BRIGHT_WHITE))
    from model_math_trans import phase_a_solve

    required = set(deps.keys())
    sp = Spinner(f"Running minisat22 on {k} role class variables...")
    sp.start()
    selected_ids = phase_a_solve(roles, role_deps, role_cfl, required, blocked=set())
    sp.stop(
        success=selected_ids is not None,
        msg=f"SAT, {len(selected_ids)} role classes selected" if selected_ids else "UNSAT"
    )

    if selected_ids is None:
        print()
        print(warn("Phase A: UNSAT, constraints are fundamentally unsatisfiable."))
        return 1

    # ── Step 5: Phase B version selection ────────────────────────────────────
    print()
    print(c("  Step 5, Phase B: concrete version selection\n", BOLD, BRIGHT_WHITE))
    from model_math_trans import solve_phased

    sp = Spinner("Selecting concrete versions (newest-first backtrack within skeleton)...")
    sp.start()
    solution = solve_phased(H, graph, required)
    sp.stop(success=solution is not None,
            msg="Solution found" if solution else "No solution, constraints unsatisfiable")

    if solution is None:
        print()
        print(warn("No satisfying assignment found. Check your constraints with 'vertex conflicts'."))
        return 1

    # ── Result ────────────────────────────────────────────────────────────────
    print()
    print(c("  Resolved versions:\n", DIM))
    rows = [[pkg, c(ver, BRIGHT_GREEN)] for pkg, ver in sorted(solution.items())]
    table(["Package", "Version"], rows)

    n_direct = len(deps)
    n_total  = len(solution)
    n_trans  = n_total - n_direct
    print(c(f"  {n_direct} direct  +  {n_trans} transitive  =  {n_total} packages total\n", DIM))
    print(ok("Trace complete. Run 'vertex resolve' to write the lock file."))
    print()
    return 0
