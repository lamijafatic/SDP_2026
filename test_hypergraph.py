"""
Standalone tests for the hypergraph dependency resolution model.

Run with:
    python test_hypergraph.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from domain.models.version import Version
from domain.models.constraint import Constraint
from model_math_trans import (
    Package, Hyperedge, HyperGraph,
    build_hypergraph, compute_role_classes, build_role_graph,
    phase_a_solve, phase_b_select, solve_phased,
)

# ─── Minimal DependencyGraph stub ────────────────────────────────────────────

class StubGraph:
    """Minimal DependencyGraph stand-in for testing."""
    def __init__(self, deps, candidates, edges):
        # deps: {name: None}  (only name matters for resolve)
        # candidates: {name: [Version, ...]}
        # edges: {(name, ver_str): [(dep_name, Constraint), ...]}
        self.dependencies = {n: None for n in deps}
        self.candidates = candidates
        self.edges = edges

    def get_candidates(self, name):
        return self.candidates.get(name, [])

    def get_dependencies(self, name, version):
        return self.edges.get((name, str(version)), [])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def ok(label):
    print(f"  [PASS] {label}")

def fail(label, detail=""):
    print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    sys.exit(1)

def check(cond, label, detail=""):
    ok(label) if cond else fail(label, detail)


# ─── Test 1: build_hypergraph ─────────────────────────────────────────────────

def test_build_hypergraph():
    print("Test 1: build_hypergraph")
    graph = StubGraph(
        deps=["requests"],
        candidates={
            "requests": [Version("2.28.0"), Version("2.31.0")],
            "urllib3":  [Version("1.26.0"), Version("2.0.0")],
        },
        edges={
            ("requests", "2.28.0"): [("urllib3", Constraint(">=1.26.0"))],
            ("requests", "2.31.0"): [("urllib3", Constraint(">=2.0.0"))],
            ("urllib3",  "1.26.0"): [],
            ("urllib3",  "2.0.0"):  [],
        },
    )

    H = build_hypergraph(graph)

    check(len(H.V) == 4, "4 nodes in hypergraph")
    dep_edges = [e for e in H.E if e.label == "dep"]
    check(len(dep_edges) == 2, "2 dep hyperedges")

    # requests@2.31.0 should only point to urllib3@2.0.0
    src_pkg = Package("requests", "2.31.0")
    edge_31 = next((e for e in dep_edges if src_pkg in e.source), None)
    check(edge_31 is not None, "edge from requests@2.31.0 exists")
    check(
        Package("urllib3", "2.0.0") in edge_31.target,
        "requests@2.31.0 → urllib3@2.0.0 in target",
    )
    check(
        Package("urllib3", "1.26.0") not in edge_31.target,
        "urllib3@1.26.0 excluded from requests@2.31.0 target (constraint >=2.0.0)",
    )


# ─── Test 2: compute_role_classes ─────────────────────────────────────────────

def test_compute_role_classes():
    print("Test 2: compute_role_classes")
    graph = StubGraph(
        deps=["A"],
        candidates={
            "A": [Version("1.0"), Version("2.0")],
            "B": [Version("1.0"), Version("2.0")],
        },
        edges={
            ("A", "1.0"): [("B", Constraint(">=1.0"))],
            ("A", "2.0"): [("B", Constraint(">=1.0"))],
            ("B", "1.0"): [],
            ("B", "2.0"): [],
        },
    )
    H = build_hypergraph(graph)
    roles = compute_role_classes(H)

    names = {rc.pkg_name for rc in roles}
    check("A" in names, "role class for A exists")
    check("B" in names, "role class for B exists")

    # B@1.0 and B@2.0 should be in the SAME role class (same target sig)
    b_roles = [rc for rc in roles if rc.pkg_name == "B"]
    check(len(b_roles) == 1, "B versions share one role class (same target signature)")
    check(len(b_roles[0].members) == 2, "B role class has 2 members")

    # Members sorted newest-first
    check(b_roles[0].members[0].version == "2.0", "B role class newest-first (2.0 first)")


# ─── Test 3: phase_a_solve — simple satisfiable case ─────────────────────────

def test_phase_a_simple():
    print("Test 3: phase_a_solve — satisfiable")
    graph = StubGraph(
        deps=["A", "B"],
        candidates={
            "A": [Version("1.0")],
            "B": [Version("1.0")],
        },
        edges={
            ("A", "1.0"): [],
            ("B", "1.0"): [],
        },
    )
    H = build_hypergraph(graph)
    roles = compute_role_classes(H)
    role_deps, role_conflicts = build_role_graph(H, roles)

    selected = phase_a_solve(roles, role_deps, role_conflicts, {"A", "B"}, blocked=set())
    check(selected is not None, "Phase A finds a solution")

    selected_names = {roles[rid].pkg_name for rid in selected}
    check("A" in selected_names, "A is selected")
    check("B" in selected_names, "B is selected")


# ─── Test 4: phase_a_solve — unsatisfiable (all blocked) ─────────────────────

def test_phase_a_unsat():
    print("Test 4: phase_a_solve — unsatisfiable when all role classes blocked")
    graph = StubGraph(
        deps=["A"],
        candidates={"A": [Version("1.0")]},
        edges={("A", "1.0"): []},
    )
    H = build_hypergraph(graph)
    roles = compute_role_classes(H)
    role_deps, role_conflicts = build_role_graph(H, roles)

    # Block all role class IDs
    all_ids = {rc.id for rc in roles}
    result = phase_a_solve(roles, role_deps, role_conflicts, {"A"}, blocked=all_ids)
    check(result is None, "Phase A returns None when all candidates are blocked")


# ─── Test 5: full solve_phased — linear dep chain ────────────────────────────

def _satisfies(solution, graph):
    """Return True if solution satisfies all inter-package constraints."""
    for pkg_name, ver_str in solution.items():
        for dep_name, constraint in graph.get_dependencies(pkg_name, ver_str):
            if dep_name in solution:
                if not constraint.is_satisfied_by(Version(solution[dep_name])):
                    return False
    return True


def test_solve_phased_chain():
    print("Test 5: solve_phased — A depends on B depends on C")
    graph = StubGraph(
        deps=["A"],
        candidates={
            "A": [Version("1.0"), Version("2.0")],
            "B": [Version("1.0"), Version("3.0")],
            "C": [Version("1.0"), Version("2.0")],
        },
        edges={
            ("A", "1.0"): [("B", Constraint(">=1.0"))],
            ("A", "2.0"): [("B", Constraint(">=3.0"))],
            ("B", "1.0"): [("C", Constraint(">=1.0"))],
            ("B", "3.0"): [("C", Constraint(">=2.0"))],
            ("C", "1.0"): [],
            ("C", "2.0"): [],
        },
    )
    H = build_hypergraph(graph)
    solution = solve_phased(H, graph, {"A"})

    check(solution is not None, "solve_phased finds a solution")
    check("A" in solution, "A is in solution")
    check("B" in solution, "B is in solution")
    check("C" in solution, "C is in solution")
    # Phase A picks the SAT-minimal role skeleton; any internally consistent
    # version set is correct (either A1+B1+C1 or A2+B3+C2 are valid).
    check(
        _satisfies(solution, graph),
        f"solution satisfies all dep constraints (got {solution})",
    )
    # Verify the two known valid combinations
    valid_combos = [
        {"A": "1.0", "B": "1.0", "C": "1.0"},
        {"A": "2.0", "B": "3.0", "C": "2.0"},
    ]
    check(
        solution in valid_combos,
        f"solution is one of the two valid version sets (got {solution})",
    )


# ─── Test 6: solve_phased — constraint forces older version ───────────────────

def test_solve_phased_constraint():
    print("Test 6: solve_phased — tight constraint forces specific version")
    graph = StubGraph(
        deps=["A"],
        candidates={
            "A": [Version("1.0")],
            "B": [Version("1.0"), Version("2.0"), Version("3.0")],
        },
        edges={
            ("A", "1.0"): [("B", Constraint(">=1.0,<2.0"))],
            ("B", "1.0"): [],
            ("B", "2.0"): [],
            ("B", "3.0"): [],
        },
    )
    H = build_hypergraph(graph)
    solution = solve_phased(H, graph, {"A"})

    check(solution is not None, "solve_phased finds a solution")
    check(solution.get("B") == "1.0", f"B constrained to 1.0, got {solution.get('B')}")


# ─── Test 7: solve_phased — conflict between two packages ─────────────────────

def test_solve_phased_conflict():
    print("Test 7: solve_phased — explicit conflict pair via repo")

    class StubRepo:
        def get_conflicts(self):
            return [("B@2.0", "C@1.0")]

    graph = StubGraph(
        deps=["A"],
        candidates={
            "A": [Version("1.0")],
            "B": [Version("1.0"), Version("2.0")],
            "C": [Version("1.0")],
        },
        edges={
            ("A", "1.0"): [
                ("B", Constraint(">=1.0")),
                ("C", Constraint(">=1.0")),
            ],
            ("B", "1.0"): [],
            ("B", "2.0"): [],
            ("C", "1.0"): [],
        },
    )

    H = build_hypergraph(graph, repo=StubRepo())
    solution = solve_phased(H, graph, {"A"})

    check(solution is not None, "solve_phased finds a solution despite conflict")
    # B@2.0 conflicts with C@1.0 — so B must fall back to 1.0
    check(
        not (solution.get("B") == "2.0" and solution.get("C") == "1.0"),
        f"conflict pair B@2.0 + C@1.0 not selected together (got B={solution.get('B')}, C={solution.get('C')})",
    )


# ─── Test 8: solve_phased — unsatisfiable returns None ───────────────────────

def test_solve_phased_unsat():
    print("Test 8: solve_phased — truly unsatisfiable returns None")
    graph = StubGraph(
        deps=["A"],
        candidates={
            "A": [Version("1.0")],
            "B": [Version("1.0")],  # only version 1.0, but A needs >=2.0
        },
        edges={
            ("A", "1.0"): [("B", Constraint(">=2.0"))],
            ("B", "1.0"): [],
        },
    )
    H = build_hypergraph(graph)
    solution = solve_phased(H, graph, {"A"})
    check(solution is None, "solve_phased returns None when constraints are unsatisfiable")


# ─── Run all tests ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_build_hypergraph,
        test_compute_role_classes,
        test_phase_a_simple,
        test_phase_a_unsat,
        test_solve_phased_chain,
        test_solve_phased_constraint,
        test_solve_phased_conflict,
        test_solve_phased_unsat,
    ]

    print("=" * 55)
    print("Hypergraph Resolution Model — Test Suite")
    print("=" * 55)
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except SystemExit:
            break
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            break

    print("=" * 55)
    print(f"Results: {passed}/{len(tests)} test groups passed")
    print("=" * 55)
