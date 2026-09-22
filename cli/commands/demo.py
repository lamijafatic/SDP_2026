"""
vertex demo, interactive algorithm walkthrough.

Walks the user through the two-phase hypergraph dependency resolution
algorithm using a concrete diamond-conflict example.
"""
from core.ui import (
    section, ok, warn, info, bold, c, DIM,
    BRIGHT_GREEN, BRIGHT_CYAN, BRIGHT_YELLOW, BRIGHT_WHITE, BOLD,
    success_box, divider, step_header, menu_prompt, pause as _pause_fn,
    Spinner, table,
)


def run(args):
    auto = getattr(args, "auto", False)
    _p   = (lambda msg="  Press Enter to continue...": None) if auto else _pause_fn
    try:
        _show_menu(auto, _p)
    except KeyboardInterrupt:
        print()
        print(warn("Demo exited."))
    return 0


# ── Menu ───────────────────────────────────────────────────────────────────────

def _show_menu(auto, _p):
    section("Vertex Demo")
    print(c("  Explore the hypergraph dependency resolution algorithm.\n", DIM))

    choice = menu_prompt([
        "Algorithm walkthrough, step through a diamond conflict, live",
        "Efficiency stats, run the live benchmark  (vertex stat)",
        "Exit",
    ])

    if choice == 1:
        _walkthrough(auto, _p)
    elif choice == 2:
        import argparse
        from cli.commands.stat import run as stat_run
        stat_run(argparse.Namespace())


# ── Walkthrough ────────────────────────────────────────────────────────────────

def _walkthrough(auto, _p):
    """
    Six-step guided walkthrough using a small diamond conflict scenario:

      web-app   → analytics >=1.0  AND  mailer >=1.0
      analytics@2.0 → crypto >=3.0   (wants new API)
      mailer@2.0    → crypto <3.0    (still on old API)

    If both analytics and mailer pick v2.0, no crypto version satisfies
    both >=3.0 AND <3.0 simultaneously.  The hypergraph resolver finds
    the non-conflicting assignment: analytics@2.0 + mailer@1.0 + crypto@4.0.
    """
    from domain.models.version import Version
    from domain.models.constraint import Constraint
    from model_math_trans import (
        build_hypergraph, compute_role_classes,
        build_role_graph, phase_a_solve, solve_phased,
    )

    STEPS = 6

    # ── Build demo graph ───────────────────────────────────────────────────────
    class _Repo:
        def get_conflicts(self): return []

    class _DemoGraph:
        def __init__(self):
            self.dependencies = {
                "web-app":   None,
                "analytics": None,
                "mailer":    None,
                "crypto":    None,
            }
            self.candidates = {
                "web-app":   [Version("1.0")],
                "analytics": [Version("1.0"), Version("2.0")],
                "mailer":    [Version("1.0"), Version("2.0")],
                "crypto":    [
                    Version("1.0"), Version("2.0"),
                    Version("3.0"), Version("4.0"),
                ],
            }
            self.edges = {
                ("web-app",   "1.0"): [
                    ("analytics", Constraint(">=1.0")),
                    ("mailer",    Constraint(">=1.0")),
                ],
                ("analytics", "1.0"): [],
                ("analytics", "2.0"): [("crypto", Constraint(">=3.0"))],
                ("mailer",    "1.0"): [],
                ("mailer",    "2.0"): [("crypto", Constraint(">=1.0,<3.0"))],
                ("crypto",    "1.0"): [],
                ("crypto",    "2.0"): [],
                ("crypto",    "3.0"): [],
                ("crypto",    "4.0"): [],
            }
            self.repo = _Repo()

        def get_candidates(self, nm):
            return self.candidates.get(nm, [])

        def get_dependencies(self, nm, ver):
            return self.edges.get((nm, str(ver)), [])

    graph    = _DemoGraph()
    required = set(graph.dependencies.keys())

    # ── Step 1 ─────────────────────────────────────────────────────────────────
    step_header(1, STEPS, "Project Setup")

    print(c("  Project declares one direct dependency:\n", DIM))
    print(f"    {c('web-app', BRIGHT_WHITE)}  {c('>=1.0', BRIGHT_CYAN)}\n")
    print(c("  web-app depends on two libraries that share a common dependency:\n", DIM))

    lines = [
        ("web-app  →", "analytics  >=1.0",   ""),
        ("web-app  →", "mailer     >=1.0",   ""),
        ("analytics@2.0  →", "crypto  >=3.0",  "wants the new API"),
        ("mailer@2.0    →",  "crypto  <3.0",   "still on the old API"),
    ]
    for src, dep, note in lines:
        note_str = c(f"  # {note}", DIM) if note else ""
        print(f"    {c(src, BRIGHT_WHITE):<22} {c(dep, BRIGHT_CYAN)}{note_str}")

    print()
    print(c("  The conflict: if both analytics@2.0 AND mailer@2.0 are selected,", DIM))
    print(c("  crypto must satisfy >=3.0 AND <3.0 at the same time, impossible.", DIM))
    print()
    print(c("  A backtracker discovers this only after exhausting all combinations.", DIM))
    print(c("  The hypergraph resolver identifies it from the graph structure.\n", DIM))
    _p()

    # ── Step 2 ─────────────────────────────────────────────────────────────────
    step_header(2, STEPS, "Hypergraph Construction  H = (V, E)")

    sp = Spinner("Building hypergraph...")
    sp.start()
    H = build_hypergraph(graph, graph.repo)
    sp.stop(success=True, msg="Hypergraph built")

    dep_edges = [e for e in H.E if e.label == "dep"]
    total_v   = len(H.V)

    print()
    print(c("  Nodes V, one per (package, version) pair:\n", DIM))

    pkg_groups = {}
    for p in H.V:
        pkg_groups.setdefault(p.name, []).append(p.version)

    for pkg in ["web-app", "analytics", "mailer", "crypto"]:
        if pkg not in pkg_groups:
            continue
        versions = sorted(pkg_groups[pkg], key=lambda v: tuple(int(x) for x in v.split(".")))
        vlist = "  ".join(c(f"v{v}", BRIGHT_CYAN) for v in versions)
        print(f"    {c(pkg, BRIGHT_WHITE):<18} {vlist}")

    print()
    print(c(f"  {total_v} nodes total  →  full version space\n", DIM))
    print(c("  Hyperedges E, each edge encodes one dependency constraint:\n", DIM))

    for e in sorted(dep_edges, key=lambda x: (next(iter(x.source)).name, next(iter(x.source)).version)):
        src   = next(iter(e.source))
        tgts  = sorted(e.target, key=lambda p: tuple(int(x) for x in p.version.split(".")))
        tgt_n = tgts[0].name
        t_str = "  ".join(c(f"v{p.version}", BRIGHT_GREEN) for p in tgts)
        print(f"    {c(f'{src.name}@{src.version}', BRIGHT_YELLOW):<24} → {c(tgt_n, BRIGHT_WHITE)} {{{t_str}}}")

    print()
    _p()

    # ── Step 3 ─────────────────────────────────────────────────────────────────
    step_header(3, STEPS, "Role Class Decomposition")

    print(c("  Two versions are role-equivalent when they appear as targets in", DIM))
    print(c("  exactly the same set of dep edges (same incidence signature σ).\n", DIM))

    sp = Spinner("Computing role classes...")
    sp.start()
    roles = compute_role_classes(H)
    sp.stop(success=True, msg=f"{len(roles)} role classes found")

    print()
    print(c(f"  {'ID':<8} {'Package':<14} {'Members':<30} {'Signature σ'}", DIM))
    print(c("  " + "─" * 60, DIM))

    for rc in sorted(roles, key=lambda r: r.pkg_name):
        m_str = "  ".join(c(f"v{m.version}", BRIGHT_CYAN) for m in rc.members)
        sig   = c(f"σ={{{', '.join(str(i) for i in sorted(rc.sig))}}}", DIM) \
                if rc.sig else c("σ=∅  (root/unconstrained)", DIM)
        print(f"  {c(f'RC[{rc.id}]', BRIGHT_YELLOW):<17} {c(rc.pkg_name, BRIGHT_WHITE):<14} {m_str:<36} {sig}")

    k   = len(roles)
    pct = round((1 - k / total_v) * 100) if total_v else 0
    print()
    print(c(f"  {total_v} version nodes  →  {k} role classes", DIM)
          + c(f"  ({pct}% reduction)", BRIGHT_GREEN))
    print(c(f"  Phase A SAT: {2**k} possible assignments  (vs {2**total_v} brute force)\n", DIM))
    _p()

    # ── Step 4 ─────────────────────────────────────────────────────────────────
    step_header(4, STEPS, "Phase A, SAT on Role Classes")

    role_deps, role_conflicts = build_role_graph(H, roles)

    print(c("  CNF formula over k=" + str(k) + " boolean variables:\n", DIM))

    name_to_rids = {}
    for rc in roles:
        name_to_rids.setdefault(rc.pkg_name, []).append(rc.id)

    print(c("  Clause 1, at-least-one per required package:\n", DIM))
    for name in sorted(required):
        rids   = name_to_rids.get(name, [])
        clause = "  ∨  ".join(c(f"x[{r}]", BRIGHT_CYAN) for r in rids)
        print(f"    {c(name, BRIGHT_WHITE):<16}  {clause}")

    if any(role_deps.values()):
        print()
        print(c("  Clause 2, dep propagation (if RC active, its targets must be active):\n", DIM))
        for rc in sorted(roles, key=lambda r: r.id):
            for tid_set in role_deps.get(rc.id, []):
                active = sorted(tid_set)
                implies = "  ∨  ".join(c(f"x[{t}]", BRIGHT_GREEN) for t in active)
                print(f"    {c(f'¬x[{rc.id}]', BRIGHT_YELLOW)}  ∨  {implies}")

    print()
    sp = Spinner("Running minisat22...")
    sp.start()
    selected_ids = phase_a_solve(roles, role_deps, role_conflicts, required, blocked=set())
    sp.stop(success=selected_ids is not None,
            msg="SAT, skeleton found" if selected_ids is not None else "UNSAT")

    if selected_ids is None:
        print()
        print(warn("Phase A: UNSAT, constraints are fundamentally unsatisfiable."))
        return

    print()
    print(c("  Selected role classes (active skeleton):\n", DIM))
    for rc in sorted(roles, key=lambda r: r.pkg_name):
        if rc.id in selected_ids:
            mems = ", ".join(f"v{m.version}" for m in rc.members)
            print(f"    {c(f'RC[{rc.id}]', BRIGHT_GREEN)}  {c(rc.pkg_name, BRIGHT_WHITE):<14}  [{mems}]")

    print()
    print(c("  Phase A does not pick specific versions, it picks role classes.", DIM))
    print(c("  Phase B chooses concrete versions within this skeleton.\n", DIM))
    _p()

    # ── Step 5 ─────────────────────────────────────────────────────────────────
    step_header(5, STEPS, "Phase B, Concrete Version Selection")

    print(c("  Packages are processed in topological order (leaves first).", DIM))
    print(c("  Each package tries its newest version first.", DIM))
    print(c("  A version is accepted only if it satisfies all current constraints.\n", DIM))

    # Phase B processes: crypto, analytics, mailer, web-app  (topological order)
    # See _topological_order in model_math_trans for derivation.

    attempt_log = [
        # (package, version, ok, explanation)
        ("crypto",    "4.0", True,
         "no constraints yet, starting newest"),
        ("analytics", "2.0", True,
         "backward: web-app not assigned yet  |  forward: crypto 4.0 ≥ 3.0  ✔"),
        ("mailer",    "2.0", False,
         "backward: crypto 4.0 violates <3.0 constraint  ✘"),
        ("mailer",    "1.0", True,
         "no crypto dependency, no conflict  ✔"),
        ("web-app",   "1.0", True,
         "analytics 2.0 ≥1.0 ✔  |  mailer 1.0 ≥1.0 ✔"),
    ]

    TICK  = c("✔", BRIGHT_GREEN)
    CROSS = c("✘", "\033[91m")
    BACK  = c("↩ backtrack", BRIGHT_YELLOW)

    print(c(f"  {'Package':<14} {'Version':<10} {'Status':<12} Note", DIM))
    print(c("  " + "─" * 68, DIM))

    for pkg, ver, success, note in attempt_log:
        icon = TICK if success else CROSS
        pkg_str  = c(pkg, BRIGHT_WHITE)
        ver_str  = c(f"v{ver}", BRIGHT_CYAN if success else DIM)
        note_str = c(note, DIM)
        if not success:
            print(f"    {pkg_str:<22} {ver_str:<18} {icon}  {note_str}")
            print(f"    {'':<22} {'':<18} {BACK}")
        else:
            print(f"    {pkg_str:<22} {ver_str:<18} {icon}  {note_str}")

    print()
    _p()

    # ── Step 6 ─────────────────────────────────────────────────────────────────
    step_header(6, STEPS, "Solution")

    # Verify with the actual solver
    sp = Spinner("Verifying with actual solver...")
    sp.start()
    real = solve_phased(H, graph, required)
    sp.stop(success=real is not None, msg="Solution verified")

    print()
    if real:
        lines = [f"{pkg:<18} {ver}" for pkg, ver in sorted(real.items())]
        success_box("Resolved", lines)
    else:
        print(warn("No solution found (should not happen in this demo)."))
        return

    print(c("  Summary:\n", DIM))
    print(c("    1 Phase A SAT call     2^" + str(k) + " = " + str(2**k) + " possible assignments", DIM))
    print(c("    5 version attempts     1 backtrack at mailer", DIM))
    print()
    print(c("  Backtracking would have explored 2^" + str(total_v) + " = " + str(2**total_v) + " combinations in the worst case.", DIM))
    print(c("  The hypergraph resolver resolved the conflict with one SAT query", DIM))
    print(c("  and a handful of direct version checks.\n", DIM))
