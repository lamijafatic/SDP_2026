from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Literal, Iterable, Optional

Label = Literal["dep", "opt", "conflict"]


@dataclass(frozen=True)
class Package:
    name: str
    version: str


@dataclass
class Hyperedge:
    source: frozenset  # frozenset[Package], typically singleton {Package}
    target: frozenset  # frozenset[Package]
    label: Label


@dataclass
class HyperGraph:
    V: set = field(default_factory=set)   # set[Package]
    E: list = field(default_factory=list)  # list[Hyperedge]

    def primal_adjacency(self):
        adj = defaultdict(set)
        for e in self.E:
            nodes = list(e.source | e.target)
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    adj[nodes[i]].add(nodes[j])
                    adj[nodes[j]].add(nodes[i])
        return adj


# ─── Legacy functions (kept for compatibility) ────────────────────────────────

def bfs_distances(adj, start):
    dist = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def refine_resolving_set(H: HyperGraph):
    adj = H.primal_adjacency()
    dists = {v: bfs_distances(adj, v) for v in H.V}

    classes = defaultdict(list)
    inc = defaultdict(list)

    for i, e in enumerate(H.E):
        for v in e.source | e.target:
            inc[v].append(i)

    for v in H.V:
        classes[tuple(sorted(inc[v]))].append(v)

    reps = {members[0] for members in classes.values()}
    W = H.V - reps

    def repr_vec(v, W_):
        Ws = sorted(W_, key=lambda p: (p.name, p.version))
        return tuple(dists[v].get(w, 10**9) for w in Ws)

    while True:
        seen, collision = {}, None
        for v in H.V:
            r = repr_vec(v, W)
            if r in seen and seen[r] != v:
                collision = (seen[r], v)
                break
            seen[r] = v
        if collision is None:
            return W
        W = W | {collision[0]}


def mcdr_solve(H: HyperGraph, roots: Iterable[Package]):
    W = sorted(
        refine_resolving_set(H),
        key=lambda p: (p.name, p.version)
    )

    adj = H.primal_adjacency()
    dists = {v: bfs_distances(adj, v) for v in H.V}
    coord = {
        v: tuple(dists[v].get(w, 10**9) for w in W)
        for v in H.V
    }

    S = set(roots)

    conflicts = {
        frozenset(e.source | e.target)
        for e in H.E if e.label == "conflict"
    }

    deps = [e for e in H.E if e.label == "dep"]

    def has_conflict(cand, S_):
        return any(cand in c and (c & S_) for c in conflicts)

    def unmet(S_):
        return [
            e for e in deps
            if (e.source & S_) and not (e.target & S_)
        ]

    def coord_dist(a, b):
        return sum(abs(x - y) for x, y in zip(a, b))

    def score(t, S_):
        if has_conflict(t, S_):
            return -10**9
        if not S_:
            return 0
        return -sum(coord_dist(coord[t], coord[s]) for s in S_) / len(S_)

    while True:
        pending = unmet(S)
        if not pending:
            return S

        e = min(
            pending,
            key=lambda x: min(
                coord_dist(
                    coord[next(iter(x.source))],
                    coord[t]
                ) for t in x.target
            )
        )

        cand = sorted(
            e.target,
            key=lambda t: score(t, S),
            reverse=True
        )

        chosen = next(
            (t for t in cand if not has_conflict(t, S)),
            None
        )

        if chosen is None:
            return None

        S.add(chosen)


# ─── HyperRes Phased Model ────────────────────────────────────────────────────
#
# Implementation of the two-phase dependency resolution algorithm:
#   Modeling  →  Metric Preprocessing  →  Role Decomposition
#   →  Phase A (Skeleton SAT)  →  Phase B (Local Instance Selection)
#
# Based on: HyperRes 2025 (Gibb et al.) and
#           Resolvability in Hypergraphs 2014 (Javaid et al.)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RoleClass:
    id: int
    pkg_name: str
    members: list   # list[Package], sorted newest-first
    sig: frozenset  # frozenset of dep-edge indices where members appear as targets


def _ver_key(p: Package):
    """Numeric sort key for a Package by version string."""
    try:
        return tuple(int(x) for x in p.version.split("."))
    except (ValueError, AttributeError):
        return (0,)


# ── Step 1: Modeling ──────────────────────────────────────────────────────────

def build_hypergraph(graph, repo=None) -> HyperGraph:
    """
    Build a labeled HyperGraph H = (V, E, L) from a DependencyGraph.

    Vertices: one Package node per (name, version) candidate.
    Dep edges: for each (pkg@ver) → dep constraint, create a hyperedge
               source={pkg@ver}, target={dep@v | constraint satisfied}, label=dep.
    Conflict edges: for each known conflict pair, label=conflict.
    """
    H = HyperGraph()
    pkg_map: dict = {}  # (name, ver_str) → Package

    for name, versions in graph.candidates.items():
        for v in versions:
            p = Package(name, str(v))
            H.V.add(p)
            pkg_map[(name, str(v))] = p

    for (pkg_name, ver_str), deps in graph.edges.items():
        src = pkg_map.get((pkg_name, ver_str))
        if src is None:
            continue
        for dep_name, constraint in deps:
            target = frozenset(
                pkg_map[(dep_name, str(dv))]
                for dv in graph.get_candidates(dep_name)
                if constraint.is_satisfied_by(dv) and (dep_name, str(dv)) in pkg_map
            )
            if target:
                H.E.append(Hyperedge(
                    source=frozenset({src}),
                    target=target,
                    label="dep",
                ))

    if repo is not None:
        try:
            for conflict in repo.get_conflicts():
                p1_str, p2_str = conflict
                pkg1, ver1 = p1_str.split("@")
                pkg2, ver2 = p2_str.split("@")
                p1 = pkg_map.get((pkg1, ver1))
                p2 = pkg_map.get((pkg2, ver2))
                if p1 and p2:
                    H.E.append(Hyperedge(
                        source=frozenset({p1}),
                        target=frozenset({p2}),
                        label="conflict",
                    ))
        except Exception:
            pass

    return H


# ── Step 2: Role Decomposition (Metric Preprocessing) ────────────────────────

def compute_role_classes(H: HyperGraph) -> list:
    """
    Partition H.V into role classes (C(i1,...,id) from Javaid et al. 2014).

    Two package versions are role-equivalent iff they have the same package name
    AND appear in exactly the same set of dep hyperedges as TARGET nodes
    (same target incidence signature → same "role" in the dependency structure).

    Packages with an empty target signature (not required by any dep edge) are
    grouped by package name alone — they are root/leaf packages.
    """
    # Compute target signature: set of dep-edge indices where p appears as target
    target_sig: dict = {}
    for i, e in enumerate(H.E):
        if e.label == "dep":
            for p in e.target:
                target_sig[p] = target_sig.get(p, frozenset()) | frozenset({i})

    # Group packages by (name, target_sig)
    groups: dict = {}
    for p in H.V:
        sig = target_sig.get(p, frozenset())
        key = (p.name, sig)
        if key not in groups:
            groups[key] = []
        groups[key].append(p)

    # Assign role class IDs in deterministic order
    sorted_keys = sorted(groups.keys(), key=lambda k: (k[0], tuple(sorted(k[1]))))

    role_classes = []
    for idx, key in enumerate(sorted_keys):
        name, sig = key
        members = sorted(groups[key], key=_ver_key, reverse=True)
        role_classes.append(RoleClass(id=idx, pkg_name=name, members=members, sig=sig))

    return role_classes


# ── Step 3: Build Role Graph (Reduced Role Hypergraph) ───────────────────────

def build_role_graph(H: HyperGraph, role_classes: list) -> tuple:
    """
    Lift dep and conflict edges to the role-class level to form the reduced
    role hypergraph used in Phase A.

    Returns:
        role_deps:      dict[role_id → list of sets of target role_ids]
                        Each set = all role classes satisfying one dep-name requirement.
        role_conflicts: list of (role_id, role_id) conflict pairs.
    """
    pkg_to_role: dict = {}
    for rc in role_classes:
        for p in rc.members:
            pkg_to_role[p] = rc.id

    # role_dep_groups[src_rid][dep_name] = set of target role ids
    role_dep_groups: dict = defaultdict(lambda: defaultdict(set))

    for e in H.E:
        if e.label != "dep":
            continue
        for src_pkg in e.source:
            src_rid = pkg_to_role.get(src_pkg)
            if src_rid is None:
                continue
            for tgt_pkg in e.target:
                tgt_rid = pkg_to_role.get(tgt_pkg)
                if tgt_rid is not None:
                    role_dep_groups[src_rid][tgt_pkg.name].add(tgt_rid)

    # Convert: role_deps[role_id] = list of sets (one per dep-name)
    role_deps: dict = {
        rid: list(name_map.values())
        for rid, name_map in role_dep_groups.items()
    }

    # Lift conflict edges to role level ONLY when both conflicting packages are
    # the sole member of their respective role class.  Partial conflicts
    # (where the role class also contains non-conflicting versions) are left
    # to Phase B's backtracking version-selection to resolve.
    role_by_id: dict = {rc.id: rc for rc in role_classes}
    role_conflicts: set = set()
    for e in H.E:
        if e.label != "conflict":
            continue
        conflict_pkgs = list(e.source | e.target)
        rids = [pkg_to_role[p] for p in conflict_pkgs if p in pkg_to_role]
        for i in range(len(rids)):
            for j in range(i + 1, len(rids)):
                rc_i = role_by_id.get(rids[i])
                rc_j = role_by_id.get(rids[j])
                if rc_i and rc_j and len(rc_i.members) == 1 and len(rc_j.members) == 1:
                    role_conflicts.add((min(rids[i], rids[j]), max(rids[i], rids[j])))

    return role_deps, list(role_conflicts)


# ── Phase A: Skeleton SAT Resolution ─────────────────────────────────────────

def phase_a_solve(
    role_classes: list,
    role_deps: dict,
    role_conflicts: list,
    required_names: set,
    blocked: set,
) -> Optional[list]:
    """
    Phase A: SAT over role classes — determines which role classes (package types)
    must be active to satisfy all required names and their transitive deps.

    SAT variables: x_i = 1 iff role class i is selected.
    Clauses:
      1. Required names: ∨ x_i for all role classes i covering name, for each required name.
      2. Dep propagation: ¬x_i ∨ (∨ x_j for j in target_role_set), per dep-name group.
      3. Conflict pairs: ¬x_i ∨ ¬x_j for each conflict.
      4. Blocked classes: ¬x_b for each b in blocked.

    Returns list of selected role class IDs, or None if UNSAT.
    """
    from pysat.formula import CNF
    from pysat.solvers import Solver

    n = len(role_classes)
    if n == 0:
        return []

    def var(rid: int) -> int:
        return rid + 1  # SAT variables are 1-indexed

    cnf = CNF()

    name_to_rids: dict = defaultdict(list)
    for rc in role_classes:
        name_to_rids[rc.pkg_name].append(rc.id)

    # Clause 1: each required name must be covered
    for name in required_names:
        active = [rid for rid in name_to_rids.get(name, []) if rid not in blocked]
        if not active:
            cnf.append([])  # Force UNSAT — no role class can cover this name
        else:
            cnf.append([var(rid) for rid in active])

    # Clause 2: dep propagation
    for rc in role_classes:
        rid = rc.id
        if rid in blocked:
            cnf.append([-var(rid)])
            continue
        for target_rid_set in role_deps.get(rid, []):
            active_targets = [j for j in target_rid_set if j not in blocked]
            if not active_targets:
                # All targets are blocked → this role class cannot be satisfied → forbid it
                cnf.append([-var(rid)])
            else:
                cnf.append([-var(rid)] + [var(j) for j in active_targets])

    # Clause 3: conflict pairs
    for (i, j) in role_conflicts:
        if i not in blocked and j not in blocked:
            cnf.append([-var(i), -var(j)])

    # Clause 4: blocked classes
    for b in blocked:
        if 0 <= b < n:
            cnf.append([-var(b)])

    with Solver(name="minisat22", bootstrap_with=cnf) as solver:
        if not solver.solve():
            return None
        model = solver.get_model()

    return [val - 1 for val in model if val > 0 and 1 <= val <= n]


# ── Phase B: Local Instance Selection ────────────────────────────────────────

def _topological_order(names: set, graph) -> list:
    """
    DFS topological sort of package names by dependency order.
    Dependencies are processed before dependents (leaves first).
    """
    visited: set = set()
    order: list = []

    def dfs(name: str):
        if name in visited:
            return
        visited.add(name)
        for v in graph.get_candidates(name):
            for dep_name, _ in graph.get_dependencies(name, v):
                if dep_name in names:
                    dfs(dep_name)
        order.append(name)

    for name in sorted(names):  # sorted for determinism
        dfs(name)

    return order


def _build_conflict_lookup(H: HyperGraph) -> dict:
    """
    Pre-build {(name, ver): set of (name, ver)} from conflict edges.
    O(|E|) once; used for O(1) per-candidate conflict checks in Phase B.
    """
    lookup: dict = {}
    for e in H.E:
        if e.label != "conflict":
            continue
        pairs = [(p.name, p.version) for p in e.source | e.target]
        for p1 in pairs:
            for p2 in pairs:
                if p1 != p2:
                    lookup.setdefault(p1, set()).add(p2)
    return lookup


def _is_version_valid(
    candidate: Package,
    solution: dict,
    graph,
    H: HyperGraph,
    conflict_lookup: Optional[dict] = None,
) -> bool:
    """
    Check whether selecting candidate is compatible with the partial solution.

    Checks:
      - Constraints imposed ON candidate by already-selected packages.
      - Constraints imposed BY candidate ON already-selected packages.
      - Explicit conflict edges (via pre-built lookup if provided, else O(|E|) scan).
    """
    from domain.models.version import Version

    pkg_name = candidate.name
    cand_ver = Version(candidate.version)
    cand_key = (pkg_name, candidate.version)

    # Conflict check — O(1) with lookup, O(|E|) fallback for backward compat
    if conflict_lookup is not None:
        for cn, cv in conflict_lookup.get(cand_key, ()):
            if solution.get(cn) == cv:
                return False
    else:
        for e in H.E:
            if e.label != "conflict":
                continue
            conflict_pairs = {(p.name, p.version) for p in e.source | e.target}
            if cand_key in conflict_pairs:
                for cn, cv in conflict_pairs:
                    if cn != pkg_name and solution.get(cn) == cv:
                        return False

    # Constraints imposed on this candidate by selected packages
    for sel_name, sel_ver_str in solution.items():
        for dep_name, constraint in graph.get_dependencies(sel_name, sel_ver_str):
            if dep_name == pkg_name:
                if not constraint.is_satisfied_by(cand_ver):
                    return False

    # Constraints this candidate imposes on other packages
    for dep_name, constraint in graph.get_dependencies(pkg_name, candidate.version):
        if dep_name in solution:
            if not constraint.is_satisfied_by(Version(solution[dep_name])):
                return False
        else:
            # Forward-check: at least one available version must satisfy
            if not any(constraint.is_satisfied_by(dv) for dv in graph.get_candidates(dep_name)):
                return False

    return True


def phase_b_select(
    H: HyperGraph,
    selected_role_ids: list,
    role_classes: list,
    graph,
) -> tuple:
    """
    Phase B: Select concrete package versions for each selected role class.

    Uses backtracking (newest-first) over the topological package order.
    Conflict checks use a pre-built O(1) lookup instead of scanning all edges.
    Tracks the deepest package that exhausted all candidates so Phase A blocks
    the correct role class on the next iteration.

    Returns (solution_dict, None) on success,
            (None, failed_role_id) if no valid combination exists for the skeleton.
    """
    role_map = {rc.id: rc for rc in role_classes}
    selected_roles = [role_map[rid] for rid in selected_role_ids if rid in role_map]

    name_to_rcs: dict = defaultdict(list)
    for rc in selected_roles:
        name_to_rcs[rc.pkg_name].append(rc)

    ordered_names = _topological_order(set(name_to_rcs.keys()), graph)
    ordered_names = [n for n in ordered_names if n in name_to_rcs]

    # Pre-sort candidates per package: newest first, deduplicated
    candidates_per_name: dict = {}
    for pkg_name in ordered_names:
        all_cands: list = []
        for rc in name_to_rcs[pkg_name]:
            all_cands.extend(rc.members)
        seen: set = set()
        deduped: list = []
        for c in sorted(all_cands, key=_ver_key, reverse=True):
            if c.version not in seen:
                seen.add(c.version)
                deduped.append(c)
        candidates_per_name[pkg_name] = deduped

    # O(|E|) once — gives O(1) per-candidate conflict check inside backtracking
    conflict_lookup = _build_conflict_lookup(H)

    # Track deepest failing package (largest idx that exhausted all candidates)
    # so Phase A blocks the correct role class on the next iteration.
    deepest_fail: list = [-1]  # mutable cell for inner function

    def backtrack(idx: int, solution: dict):
        if idx == len(ordered_names):
            return solution
        pkg_name = ordered_names[idx]
        for candidate in candidates_per_name[pkg_name]:
            if _is_version_valid(candidate, solution, graph, H, conflict_lookup):
                result = backtrack(idx + 1, {**solution, pkg_name: candidate.version})
                if result is not None:
                    return result
        # All candidates at this index exhausted — record deepest failure
        if idx > deepest_fail[0]:
            deepest_fail[0] = idx
        return None

    result = backtrack(0, {})
    if result is None:
        fail_idx = max(deepest_fail[0], 0)
        fail_idx = min(fail_idx, len(ordered_names) - 1)
        failed_name = ordered_names[fail_idx] if ordered_names else None
        failed_rid = name_to_rcs[failed_name][0].id if failed_name else -1
        return None, failed_rid
    return result, None


# ── Main entry point: full two-phase algorithm ────────────────────────────────

def solve_phased(H: HyperGraph, graph, required_names: set) -> Optional[dict]:
    """
    Full HyperRes phased resolution:

      1. Metric Preprocessing: compute role classes from H (role decomposition).
      2. Build reduced role hypergraph.
      3. Loop:
           Phase A — SAT on role graph → selected role class skeleton.
           Phase B — greedy version selection → concrete solution.
           If Phase B fails for a role class, block it and repeat from Phase A.

    Returns {pkg_name: version_str} on success, or None if no solution exists.
    """
    role_classes = compute_role_classes(H)
    role_deps, role_conflicts = build_role_graph(H, role_classes)

    blocked: set = set()
    max_iterations = len(role_classes) + 1

    for _ in range(max_iterations):
        selected_ids = phase_a_solve(
            role_classes, role_deps, role_conflicts, required_names, blocked
        )
        if selected_ids is None:
            return None  # Phase A UNSAT — constraints are fundamentally unsatisfiable

        solution, failed_rid = phase_b_select(H, selected_ids, role_classes, graph)
        if solution is not None:
            return solution

        # Block the failed role class and try again with a different skeleton
        blocked.add(failed_rid)

    return None  # Exhausted all role class combinations without a valid solution
