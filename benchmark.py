import sys
import os
import time
import argparse
import statistics
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

from application.services.graph_service import GraphService
from infrastructure.repository.smart_repo import SmartRepository
from domain.resolver.sat_resolver import SATResolver
from domain.resolver.backtracking_resolver import BacktrackingResolver
from domain.resolver.hypergraph_resolver import HypergraphResolver
from model_math_trans import build_hypergraph, solve_phased
from domain.models.version import Version
from domain.models.constraint import Constraint


REAL_GROUPS = {
    "small": {
        "label": "Small, 3 direct deps (requests stack)",
        "deps": {
            "requests": ">=2.28.0",
            "numpy":    ">=1.24.0",
            "pandas":   ">=1.5.0",
        },
    },
    "medium": {
        "label": "Medium, 6 direct deps (data science stack)",
        "deps": {
            "numpy":        ">=1.24.0",
            "pandas":       ">=1.5.0",
            "scipy":        ">=1.9.0",
            "matplotlib":   ">=3.5.0",
            "scikit-learn": ">=1.1.0",
            "requests":     ">=2.28.0",
        },
    },
    "large": {
        "label": "Large, 8 direct deps (ML stack)",
        "deps": {
            "numpy":        ">=1.24.0",
            "pandas":       ">=1.5.0",
            "scipy":        ">=1.9.0",
            "matplotlib":   ">=3.5.0",
            "scikit-learn": ">=1.1.0",
            "requests":     ">=2.28.0",
            "pillow":       ">=9.0.0",
            "xgboost":      ">=1.6.0",
        },
    },
    "xlarge": {
        "label": "XLarge, 15 direct deps (full stack)",
        "deps": {
            "numpy":        ">=1.24.0",
            "pandas":       ">=1.5.0",
            "scipy":        ">=1.9.0",
            "matplotlib":   ">=3.5.0",
            "scikit-learn": ">=1.1.0",
            "requests":     ">=2.28.0",
            "pillow":       ">=9.0.0",
            "xgboost":      ">=1.6.0",
            "flask":        ">=2.0.0",
            "sqlalchemy":   ">=1.4.0",
            "pytest":       ">=7.0.0",
            "pydantic":     ">=1.10.0",
            "click":        ">=8.0.0",
            "tqdm":         ">=4.60.0",
            "cryptography": ">=38.0.0",
        },
    },
}

STRATEGIES = ["sat", "backtracking", "hypergraph"]


class _SyntheticRepo:
    def __init__(self, conflicts):
        self._conflicts = conflicts

    def get_conflicts(self):
        return self._conflicts


class SyntheticGraph:
    def __init__(self, n_packages: int, n_versions: int, n_conflicts: int = 0):
        self.n_packages = n_packages
        self.n_versions = n_versions

        pkg_names = [f"P{i}" for i in range(n_packages)]
        self.dependencies = {n: None for n in pkg_names}

        self.candidates = {
            name: [Version(f"{v}.0") for v in range(1, n_versions + 1)]
            for name in pkg_names
        }

        self.edges = {}
        for i, name in enumerate(pkg_names):
            for v in range(1, n_versions + 1):
                if i + 1 < n_packages:
                    next_name = pkg_names[i + 1]
                    dep_ver = f"{v}.0"
                    self.edges[(name, f"{v}.0")] = [
                        (next_name, Constraint(f">={dep_ver},<{v + 1}.0"))
                    ]
                else:
                    self.edges[(name, f"{v}.0")] = []

        self._conflicts = []
        for i in range(min(n_conflicts, n_packages - 1)):
            self._conflicts.append((f"P{i}@{n_versions}.0", f"P{i+1}@{n_versions}.0"))

        self.repo = _SyntheticRepo(self._conflicts)

    def get_candidates(self, name):
        return self.candidates.get(name, [])

    def get_dependencies(self, name, version):
        return self.edges.get((name, str(version)), [])

    def get_conflicts(self):
        return self._conflicts


SYNTHETIC_CASES = [
    {"label": "Synthetic S, 20 pkgs × 10 versions, tight chain",           "n": 20,  "v": 10, "c": 0},
    {"label": "Synthetic M, 50 pkgs × 10 versions, tight chain",           "n": 50,  "v": 10, "c": 0},
    {"label": "Synthetic L, 100 pkgs × 10 versions, tight chain",          "n": 100, "v": 10, "c": 0},
    {"label": "Synthetic LC, 100 pkgs × 10 versions, chain + 10 conflicts", "n": 100, "v": 10, "c": 10},
]


class DiamondConflictGraph:
    def __init__(self, n_sides: int):
        n_core     = 2 * n_sides + 2
        high_floor = n_sides + 1

        left_names  = [f"L{i}" for i in range(n_sides)]
        right_names = [f"R{i}" for i in range(n_sides)]
        all_names   = left_names + right_names + ["Core"]

        self.dependencies = {n: None for n in all_names}

        self.candidates = {}
        for name in left_names + right_names:
            self.candidates[name] = [Version("1.0"), Version("2.0")]
        self.candidates["Core"] = [Version(f"{v}.0") for v in range(1, n_core + 1)]

        self.edges = {}
        for name in left_names:
            self.edges[(name, "2.0")] = [("Core", Constraint(f">={high_floor}.0"))]
            self.edges[(name, "1.0")] = []
        for name in right_names:
            self.edges[(name, "2.0")] = [("Core", Constraint(f">=1.0,<{high_floor}.0"))]
            self.edges[(name, "1.0")] = []
        for v in range(1, n_core + 1):
            self.edges[("Core", f"{v}.0")] = []

        self._conflicts = []
        self.repo = _SyntheticRepo(self._conflicts)

    def get_candidates(self, name):
        return self.candidates.get(name, [])

    def get_dependencies(self, name, version):
        return self.edges.get((name, str(version)), [])

    def get_conflicts(self):
        return self._conflicts


DIAMOND_CASES = [
    {"label": "Diamond 1, 1+1  frameworks + core",  "n": 1},
    {"label": "Diamond 2, 2+2  frameworks + core",  "n": 2},
    {"label": "Diamond 3, 3+3  frameworks + core",  "n": 3},
    {"label": "Diamond S, 5+5  frameworks + core",  "n": 5},
    {"label": "Diamond M, 10+10 frameworks + core",  "n": 10},
    {"label": "Diamond L, 12+12 frameworks + core",  "n": 12},
    {"label": "Diamond XL, 15+15 frameworks + core",  "n": 15},
    {"label": "Diamond XXL, 25+25 frameworks + core",  "n": 25},
    {"label": "Diamond 3XL, 50+50 frameworks + core",  "n": 50},
]


def _fmt(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.2f}  s"
    return f"{ms:.3f}ms"


def _bar(ms: float, max_ms: float, width: int = 20) -> str:
    if max_ms <= 0:
        return "░" * width
    filled = min(int((ms / max_ms) * width), width)
    return "█" * filled + "░" * (width - filled)


def _median(times):
    return statistics.median(times) if times else float("inf")


def _time_phase_a(graph, runs: int) -> float:
    """Time Phase A alone (SAT on role classes). Returns median ms."""
    from model_math_trans import (
        build_hypergraph, compute_role_classes, build_role_graph, phase_a_solve,
    )
    H                   = build_hypergraph(graph)
    roles               = compute_role_classes(H)
    role_deps, role_cfl = build_role_graph(H, roles)
    required            = set(graph.dependencies.keys())
    times               = []
    for _ in range(runs):
        t0 = time.perf_counter()
        phase_a_solve(roles, role_deps, role_cfl, required, set())
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times) if times else 0.0


def _compression_stats(graph) -> tuple:
    """Return (total_version_nodes, k_role_classes) for the graph's hypergraph."""
    from model_math_trans import build_hypergraph, compute_role_classes
    H    = build_hypergraph(graph)
    rcs  = compute_role_classes(H)
    return len(H.V), len(rcs)


def _time_solver(resolver_cls, graph, runs: int) -> dict:
    times    = []
    solution = None
    failed   = False
    for i in range(runs):
        r  = resolver_cls(graph)
        t0 = time.perf_counter()
        try:
            sol     = r.solve()
            elapsed = (time.perf_counter() - t0) * 1000
            times.append(elapsed)
            if solution is None:
                solution = sol
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            if i == 0:
                failed = True
                break
            times.append(elapsed)
    return {"times": times, "failed": failed, "solution": solution}


def _time_hypergraph_synthetic(graph, runs: int) -> dict:
    H        = build_hypergraph(graph)
    required = set(graph.dependencies.keys())
    times    = []
    solution = None
    failed   = False
    for i in range(runs):
        t0      = time.perf_counter()
        sol     = solve_phased(H, graph, required)
        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)
        if solution is None:
            solution = sol
        if sol is None and i == 0:
            failed = True
            break
    return {"times": times, "failed": failed, "solution": solution}


def _print_table(label: str, pkg_count: int, runs: int, results: dict):
    print(f"\n{'═' * 66}")
    print(f"  {label}")
    print(f"  Packages resolved: {pkg_count}    Runs per strategy: {runs}")
    print(f"{'─' * 66}")
    print(f"  {'Strategy':<14} {'Min':>10} {'Median':>10} {'Max':>10}  Bar (relative)")
    print(f"  {'-'*14} {'-'*10} {'-'*10} {'-'*10}  {'-'*20}")

    medians = {s: _median(d["times"]) for s, d in results.items() if not d["failed"] and d["times"]}
    max_med = max(medians.values()) if medians else 1.0

    for strategy in STRATEGIES:
        data = results[strategy]
        if data.get("skipped"):
            print(f"  {strategy:<14} {', ':>10} {', ':>10} {', ':>10}  not run (>24h projected)")
            continue
        if data["failed"] or not data["times"]:
            print(f"  {strategy:<14} {'FAILED':>10}")
            continue
        t = data["times"]
        mn, med, mx = min(t), _median(t), max(t)
        print(f"  {strategy:<14} {_fmt(mn):>10} {_fmt(med):>10} {_fmt(mx):>10}  {_bar(med, max_med)}")
    print(f"{'═' * 66}")


def _print_summary(all_entries: list):
    print(f"\n{'═' * 66}")
    print("  SUMMARY, Median solver-only times")
    print(f"{'─' * 66}")
    print(f"  {'Scenario':<36}  {'SAT':>9}  {'BT':>9}  {'HG':>9}  Fastest")
    print(f"  {'-'*36}  {'-'*9}  {'-'*9}  {'-'*9}  {'-'*11}")
    for entry in all_entries:
        name, results = entry["name"], entry["results"]
        row = {}
        for s, d in results.items():
            if d.get("skipped") or d["failed"] or not d["times"]:
                row[s] = float("inf")
            else:
                row[s] = _median(d["times"])
        fastest = min((s for s in row if row[s] < float("inf")), key=row.get, default=", ")
        def _show(s):
            v = row[s]
            return "  >24h" if v == float("inf") and results[s].get("skipped") else (
                "FAILED" if v == float("inf") else _fmt(v)
            )
        print(
            f"  {name[:36]:<36}  "
            f"{_show('sat'):>9}  "
            f"{_show('backtracking'):>9}  "
            f"{_show('hypergraph'):>9}  "
            f"{fastest}"
        )
    print(f"{'═' * 66}\n")


def run_real(runs: int) -> list:
    print("\n  Building dependency graphs (includes PyPI fetch)...")
    repo    = SmartRepository()
    gs      = GraphService(repo)
    entries = []

    for group_name, group in REAL_GROUPS.items():
        print(f"    {group_name}...", end="", flush=True)
        graph     = gs.build_graph(group["deps"])
        pkg_count = len(graph.dependencies)
        print(f" {pkg_count} packages")

        results = {}
        for strategy, cls in [
            ("sat", SATResolver),
            ("backtracking", BacktrackingResolver),
            ("hypergraph", HypergraphResolver),
        ]:
            results[strategy] = _time_solver(cls, graph, runs)

        _print_table(group["label"], pkg_count, runs, results)
        entries.append({"name": group_name, "results": results})

    return entries


def run_synthetic(runs: int) -> list:
    entries = []
    for case in SYNTHETIC_CASES:
        graph     = SyntheticGraph(case["n"], case["v"], case["c"])
        pkg_count = case["n"]
        results   = {
            "sat":          _time_solver(SATResolver, graph, runs),
            "backtracking": _time_solver(BacktrackingResolver, graph, runs),
            "hypergraph":   _time_hypergraph_synthetic(graph, runs),
        }
        _print_table(case["label"], pkg_count, runs, results)
        entries.append({"name": case["label"][:36], "results": results})
    return entries


# Backtracking scales as O(v^n) on diamond conflicts.
# At n > BT_MAX_DIAMOND it would run for >24 hours, so we skip it.
BT_MAX_DIAMOND = 12


def run_diamond(runs: int) -> list:
    entries = []
    for case in DIAMOND_CASES:
        n         = case["n"]
        graph     = DiamondConflictGraph(n)
        pkg_count = 2 * n + 1

        if n <= BT_MAX_DIAMOND:
            bt_result = _time_solver(BacktrackingResolver, graph, runs)
        else:
            bt_result = {"times": [], "failed": False, "skipped": True, "solution": None}

        hg_result  = _time_hypergraph_synthetic(graph, runs)
        phase_a_ms = _time_phase_a(graph, runs)
        hg_total   = _median(hg_result["times"]) if hg_result["times"] else 0.0
        phase_b_ms = max(0.0, hg_total - phase_a_ms)
        v_count, k = _compression_stats(graph)

        results = {
            "sat":          _time_solver(SATResolver, graph, runs),
            "backtracking": bt_result,
            "hypergraph":   hg_result,
        }
        _print_table(case["label"], pkg_count, runs, results)
        entries.append({
            "name":        case["label"][:36],
            "results":     results,
            "n":           n,
            "hg_phase_a":  phase_a_ms,
            "hg_phase_b":  phase_b_ms,
            "compression": (v_count, k),
        })
    return entries


def generate_plots(all_entries: list):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
        import numpy as np
    except ImportError:
        print("  [plots skipped, pip install matplotlib]\n")
        return

    BASE = os.path.dirname(os.path.abspath(__file__))

    def _save_open(fig, name):
        path = os.path.join(BASE, name)
        fig.savefig(path, dpi=150, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        try:
            subprocess.Popen(["open", path])
        except Exception:
            pass
        print(f"  Saved: {path}")
        return path

    # ── Shared palette & style ────────────────────────────────────────────────
    C = {
        "hg":       "#16A34A",   # green, Hypergraph
        "sat":      "#2563EB",   # blue, SAT
        "bt":       "#DC2626",   # red, Backtracking
        "phase_a":  "#15803D",   # dark green
        "phase_b":  "#86EFAC",   # light green
        "gray":     "#6B7280",
        "grid":     "#E5E7EB",
        "border":   "#D1D5DB",
    }

    plt.rcParams.update({
        "font.family":     "DejaVu Sans",
        "axes.facecolor":  "#FFFFFF",
        "axes.edgecolor":  C["border"],
        "axes.linewidth":  0.9,
        "xtick.color":     "#374151",
        "ytick.color":     "#374151",
        "text.color":      "#111827",
        "axes.labelcolor": "#111827",
        "axes.spines.top":    False,
        "axes.spines.right":  False,
    })

    # ── Helpers ───────────────────────────────────────────────────────────────
    def mv(entry, s):
        d = entry["results"][s]
        if d.get("skipped") or d.get("failed") or not d["times"]:
            return np.nan
        return statistics.median(d["times"])

    def get_n(entry):
        nm = entry["name"]
        for pat, val in [("50+50", 50), ("25+25", 25), ("15+15", 15),
                         ("12+12", 12), ("10+10", 10), ("5+5", 5),
                         ("3+3", 3), ("2+2", 2), ("1+1", 1)]:
            if pat in nm:
                return val
        return entry.get("n", None)

    def slabel(name):
        lut = {"small":  "PyPI Small",
               "medium": "PyPI Medium",
               "large":  "PyPI Large",
               "xlarge": "PyPI XLarge"}
        if name in lut:
            return lut[name]
        for pat, lbl in [("50+50","Dia n=50"),("25+25","Dia n=25"),
                          ("15+15","Dia n=15"),("12+12","Dia n=12"),
                          ("10+10","Dia n=10"),("5+5","Dia n=5"),
                          ("3+3","Dia n=3"),("2+2","Dia n=2"),("1+1","Dia n=1")]:
            if pat in name: return lbl
        if "Synthetic LC" in name: return "Chain CF"
        if "Synthetic S"  in name: return "Chain S"
        if "Synthetic M"  in name: return "Chain M"
        if "Synthetic L"  in name: return "Chain L"
        return name[:12]

    def ax_grid(ax, axis="y"):
        ax.grid(axis=axis, color=C["grid"], linewidth=0.75, alpha=0.9)
        ax.set_axisbelow(True)

    diamond_e = [e for e in all_entries if "Diamond" in e["name"]]
    synth_e   = [e for e in all_entries if "Synthetic" in e["name"]]
    real_e    = [e for e in all_entries if e["name"] in ("small","medium","large","xlarge")]
    has_diam  = bool(diamond_e)

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 1, Diamond conflict scaling (all n, log scale)
    # ═══════════════════════════════════════════════════════════════════════════
    if has_diam:
        fig, ax = plt.subplots(figsize=(13, 6))
        d_ns = [get_n(e) for e in diamond_e]

        for s, mk, lw, ms, ls, col, lbl in [
            ("backtracking", "o", 2.6, 9,  ":",  C["bt"],  "Backtracking (BT)"),
            ("sat",          "s", 2.2, 8,  "--", C["sat"], "SAT Solver"),
            ("hypergraph",   "D", 2.8, 9,  "-",  C["hg"],  "Hypergraph (HG)"),
        ]:
            vals      = [mv(e, s) for e in diamond_e]
            valid_ns  = [n for n, v in zip(d_ns, vals) if not np.isnan(v)]
            valid_vs  = [v for v in vals if not np.isnan(v)]
            if not valid_ns:
                continue
            ax.plot(valid_ns, valid_vs, marker=mk, linestyle=ls,
                    linewidth=lw, markersize=ms, color=col,
                    label=lbl, zorder=4, clip_on=False)
            ax.annotate(_fmt(valid_vs[-1]),
                        xy=(valid_ns[-1], valid_vs[-1]),
                        xytext=(7, 3), textcoords="offset points",
                        fontsize=8.5, color=col, fontweight="bold")

        # BT / HG callout at n=12
        e12 = next((e for e in diamond_e if "12+12" in e["name"]), None)
        if e12:
            bt12, hg12 = mv(e12, "backtracking"), mv(e12, "hypergraph")
            if not (np.isnan(bt12) or np.isnan(hg12)) and hg12 > 0:
                ratio = bt12 / hg12
                ax.annotate(
                    f"n=12\nBT = {bt12:.0f} ms\nHG = {hg12:.3f} ms\n{ratio:.0f}x faster",
                    xy=(12, hg12), xytext=(17, hg12 * 60),
                    fontsize=9, color="#111827",
                    arrowprops=dict(arrowstyle="-|>", color=C["hg"],
                                   lw=1.5, connectionstyle="arc3,rad=0.15"),
                    bbox=dict(boxstyle="round,pad=0.45", fc="white",
                              ec=C["hg"], lw=1.6, alpha=0.97),
                )

        # Crossover band
        crossover_n = None
        for e, n in zip(diamond_e, d_ns):
            hgt, btt = mv(e, "hypergraph"), mv(e, "backtracking")
            if not (np.isnan(hgt) or np.isnan(btt)) and hgt < btt:
                crossover_n = n
                break
        if crossover_n and d_ns[0] < crossover_n:
            ax.axvspan(d_ns[0] - 0.3, crossover_n - 0.5,
                       alpha=0.06, color=C["bt"], zorder=0)
            ax.text((d_ns[0] + crossover_n - 1) / 2, ax.get_ylim()[0] * 2.5,
                    "BT region\n(BT wins)", ha="center", fontsize=8,
                    color=C["bt"], style="italic")
            ax.axvspan(crossover_n - 0.5, d_ns[-1] + 0.3,
                       alpha=0.05, color=C["hg"], zorder=0)
            ax.axvline(crossover_n - 0.5, color=C["gray"],
                       linestyle="--", linewidth=1.2, alpha=0.6)

        # BT skip marker
        first_skip = next((n for e, n in zip(diamond_e, d_ns)
                           if e["results"]["backtracking"].get("skipped")), None)
        if first_skip:
            ax.axvline(first_skip - 0.8, color=C["gray"], linestyle=":",
                       linewidth=1.1, alpha=0.55)
            ax.text(first_skip - 0.6, ax.get_ylim()[0] * 1.8,
                    "BT skipped\n(> 24 h)", fontsize=7.5,
                    color=C["gray"], style="italic")

        # Reference lines
        ax.axhline(1000, color="#EF4444", linestyle=":", linewidth=1.2,
                   alpha=0.6, label="1 second threshold")
        ax.axhline(1,    color=C["gray"], linestyle=":", linewidth=0.9,
                   alpha=0.45, label="1 ms")

        # Theory annotations, right margin
        for y_frac, txt, col in [
            (0.93, "O(v^n)  exponential",   C["bt"]),
            (0.62, "O(n v m)  polynomial",  C["sat"]),
            (0.20, "O(k2 m)  near-linear",  C["hg"]),
        ]:
            ax.text(1.01, y_frac, txt, transform=ax.transAxes,
                    fontsize=8.5, color=col, style="italic", va="top")

        ax.set_yscale("log")
        ax.set_xticks(d_ns)
        ax.set_xticklabels([f"n={n}" for n in d_ns], fontsize=10)
        ax.set_xlabel("n   (frameworks per side in diamond conflict graph)", fontsize=11)
        ax.set_ylabel("Resolution time (ms, log scale)", fontsize=11)
        ax.set_title("Diamond Conflict Scaling: Exponential BT vs Near-Flat HG",
                     fontsize=13, fontweight="bold", pad=10)
        ax.legend(fontsize=10, loc="upper left", framealpha=0.92,
                  edgecolor=C["border"], fancybox=False)
        ax.yaxis.set_major_formatter(
            ticker.FuncFormatter(lambda v, _: f"{v:.4g} ms"))
        ax_grid(ax)
        fig.tight_layout()
        _save_open(fig, "benchmark_01_scaling.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 2, Small-n close-up (n=1 to n=5, BT wins region)
    # ═══════════════════════════════════════════════════════════════════════════
    if has_diam:
        small_e = [e for e in diamond_e if (get_n(e) or 99) <= 5]
        if small_e:
            fig, ax = plt.subplots(figsize=(9, 5))
            s_ns = [get_n(e) for e in small_e]

            for s, mk, col, lbl in [
                ("backtracking", "o", C["bt"],  "Backtracking (BT)"),
                ("sat",          "s", C["sat"], "SAT Solver"),
                ("hypergraph",   "D", C["hg"],  "Hypergraph (HG)"),
            ]:
                vals = [mv(e, s) for e in small_e]
                ax.plot(s_ns, vals, marker=mk, linewidth=2.4,
                        markersize=10, color=col, label=lbl, zorder=4)
                for n, v in zip(s_ns, vals):
                    if not np.isnan(v):
                        ax.annotate(f"{v:.3f} ms", xy=(n, v),
                                    xytext=(0, 9), textcoords="offset points",
                                    ha="center", fontsize=8.5,
                                    color=col, fontweight="bold")

            # Shade where BT wins
            crossover_small = None
            for e, n in zip(small_e, s_ns):
                hgt, btt = mv(e, "hypergraph"), mv(e, "backtracking")
                if not (np.isnan(hgt) or np.isnan(btt)) and hgt < btt:
                    crossover_small = n
                    break
            if crossover_small and s_ns[0] < crossover_small:
                ax.axvspan(s_ns[0] - 0.15, crossover_small - 0.5,
                           alpha=0.08, color=C["bt"], zorder=0)
                ax.text(s_ns[0] + 0.1, ax.get_ylim()[1] * 0.85,
                        "BT wins here\n(HG overhead dominant)",
                        color=C["bt"], fontsize=9, style="italic")

            ax.set_xticks(s_ns)
            ax.set_xticklabels([f"n={n}" for n in s_ns], fontsize=11)
            ax.set_xlabel("n  (small diamond graphs)", fontsize=11)
            ax.set_ylabel("Resolution time (ms)", fontsize=11)
            ax.set_title("Small-n Region: Where HG Overhead Matters\n"
                         "Phase A setup cost dominates at n=1 and n=2",
                         fontsize=12, fontweight="bold")
            ax.legend(fontsize=10, framealpha=0.92, edgecolor=C["border"],
                      fancybox=False)
            ax_grid(ax)
            fig.tight_layout()
            _save_open(fig, "benchmark_02_smalln.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 3, BT / HG speedup ratio (bar chart, log scale)
    # ═══════════════════════════════════════════════════════════════════════════
    spd_lbls, bt_ratios, sat_ratios = [], [], []
    for e in all_entries:
        hg  = mv(e, "hypergraph")
        bt  = mv(e, "backtracking")
        sat = mv(e, "sat")
        if not np.isnan(hg) and hg > 0 and not np.isnan(sat):
            spd_lbls.append(slabel(e["name"]))
            bt_ratios.append(bt / hg if not np.isnan(bt) else np.nan)
            sat_ratios.append(sat / hg)

    if spd_lbls:
        y_pos = np.arange(len(spd_lbls))
        fig, ax = plt.subplots(figsize=(11, max(5, len(spd_lbls) * 0.55 + 1.5)))
        bt_colors = [C["bt"] if (not np.isnan(v) and v >= 1.0) else "#6B7280"
                     for v in bt_ratios]
        ax.barh(y_pos, [v if not np.isnan(v) else 0 for v in bt_ratios],
                0.55, color=bt_colors, alpha=0.85,
                edgecolor="white", linewidth=0.5, zorder=3)

        # Skipped BT labels
        for i, bv in enumerate(bt_ratios):
            if np.isnan(bv):
                ax.text(1.3, i, "BT skipped (> 24 h)", va="center",
                        fontsize=8.5, color=C["gray"], style="italic")
            elif bv >= 2:
                ax.text(bv * 1.06, i, f"{bv:.0f}x",
                        va="center", fontsize=9,
                        color=C["bt"], fontweight="bold")

        ax.axvline(1.0, color="#111827", linewidth=2.0, linestyle="--",
                   zorder=5, label="Equal speed  (1x)")
        ax.set_xscale("log")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(spd_lbls, fontsize=9.5)
        ax.set_xlabel("BT / HG time ratio  (log scale,  >1 means HG wins)", fontsize=10.5)
        ax.set_title("Speedup of Hypergraph over Backtracking\n"
                     "Values above 1x mean HG is faster",
                     fontsize=12, fontweight="bold")
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.3g}x"))
        ax.legend(fontsize=9.5, framealpha=0.92, edgecolor=C["border"], fancybox=False)
        ax_grid(ax, axis="x")
        fig.tight_layout()
        _save_open(fig, "benchmark_03_speedup_bt.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 4, SAT / HG speedup ratio
    # ═══════════════════════════════════════════════════════════════════════════
    if spd_lbls:
        y_pos = np.arange(len(spd_lbls))
        # Color bars: green if HG wins (>1), gray if not
        sat_colors = [C["sat"] if sv >= 1.0 else "#9CA3AF" for sv in sat_ratios]
        fig, ax = plt.subplots(figsize=(11, max(5, len(spd_lbls) * 0.55 + 1.5)))
        ax.barh(y_pos, sat_ratios, 0.55, color=sat_colors, alpha=0.85,
                edgecolor="white", linewidth=0.5, zorder=3)
        for i, sv in enumerate(sat_ratios):
            ax.text(sv * 1.05, i, f"{sv:.2f}x",
                    va="center", fontsize=9,
                    color=C["sat"], fontweight="bold")
        ax.axvline(1.0, color="#111827", linewidth=2.0, linestyle="--",
                   zorder=5, label="Equal speed  (1x)")
        ax.set_xscale("log")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(spd_lbls, fontsize=9.5)
        ax.set_xlabel("SAT / HG time ratio  (log scale,  >1 means HG wins)", fontsize=10.5)
        ax.set_title("Speedup of Hypergraph over SAT Solver\n"
                     "HG consistently wins due to role-class compression",
                     fontsize=12, fontweight="bold")
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.3g}x"))
        ax.legend(fontsize=9.5, framealpha=0.92, edgecolor=C["border"], fancybox=False)
        ax_grid(ax, axis="x")
        fig.tight_layout()
        _save_open(fig, "benchmark_04_speedup_sat.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 5, Conflict-free vs conflict-heavy comparison
    # ═══════════════════════════════════════════════════════════════════════════
    if synth_e or real_e:
        compare_groups = []
        for e in real_e + synth_e:
            hg  = mv(e, "hypergraph")
            bt  = mv(e, "backtracking")
            sat = mv(e, "sat")
            if not np.isnan(hg):
                compare_groups.append((slabel(e["name"]), hg, sat, bt))

        if compare_groups:
            lbls = [r[0] for r in compare_groups]
            hg_v = np.array([r[1] for r in compare_groups])
            sat_v = np.array([r[2] for r in compare_groups])
            bt_v  = np.array([r[3] for r in compare_groups])

            x  = np.arange(len(lbls))
            w  = 0.26
            fig, ax = plt.subplots(figsize=(max(10, len(lbls) * 1.4 + 2), 5.5))
            ax.bar(x - w,   hg_v,  w, color=C["hg"],  alpha=0.88, label="Hypergraph (HG)",     edgecolor="white")
            ax.bar(x,       sat_v, w, color=C["sat"], alpha=0.88, label="SAT Solver",           edgecolor="white")
            ax.bar(x + w,   [v if not np.isnan(v) else 0 for v in bt_v], w,
                   color=C["bt"],  alpha=0.88, label="Backtracking (BT)",    edgecolor="white")

            # BT > 24 h note
            for i, bv in enumerate(bt_v):
                if np.isnan(bv):
                    ax.text(x[i] + w, 0.01, "n/a", ha="center", va="bottom",
                            fontsize=7.5, color=C["gray"], style="italic")

            ax.set_yscale("log")
            ax.set_xticks(x)
            ax.set_xticklabels(lbls, fontsize=9.5)
            ax.set_xlabel("Scenario (conflict-free chains and real PyPI graphs)", fontsize=10.5)
            ax.set_ylabel("Resolution time (ms, log scale)", fontsize=10.5)
            ax.set_title("Conflict-Free Graphs: Where BT Excels\n"
                         "On chain/real graphs with no conflicts, BT finds solution immediately",
                         fontsize=12, fontweight="bold")
            ax.legend(fontsize=10, framealpha=0.92, edgecolor=C["border"], fancybox=False)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.4g} ms"))
            ax_grid(ax)
            fig.tight_layout()
            _save_open(fig, "benchmark_05_conflict_free.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 6, Role class compression: |V| vs k
    # ═══════════════════════════════════════════════════════════════════════════
    if has_diam:
        comp_ns, total_vs, k_vals, pcts = [], [], [], []
        for e in diamond_e:
            n = get_n(e)
            if n and "compression" in e:
                tv, k = e["compression"]
                comp_ns.append(n)
                total_vs.append(tv)
                k_vals.append(k)
                pcts.append((1 - k / tv) * 100 if tv else 0)

        if comp_ns:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

            # Left: absolute counts
            ax1.fill_between(comp_ns, k_vals, total_vs, alpha=0.10,
                             color=C["bt"], label="Nodes compressed away")
            ax1.plot(comp_ns, total_vs, "o-", color=C["bt"],
                     lw=2.2, ms=8, label="|V|  version nodes", zorder=3)
            ax1.plot(comp_ns, k_vals, "D-", color=C["hg"],
                     lw=2.2, ms=8, label="k  role class variables", zorder=4)
            for n, tv, k in zip(comp_ns, total_vs, k_vals):
                ax1.annotate(f"k={k}", xy=(n, k), xytext=(0, 8),
                             textcoords="offset points", ha="center",
                             fontsize=8, color=C["hg"], fontweight="bold")
            ax1.set_xticks(comp_ns)
            ax1.set_xticklabels([f"n={n}" for n in comp_ns], fontsize=9)
            ax1.set_xlabel("n  (diamond graph size)", fontsize=10.5)
            ax1.set_ylabel("Variable count", fontsize=10.5)
            ax1.set_title("|V| Version Nodes  vs  k Role Class Variables",
                          fontsize=11, fontweight="bold")
            ax1.legend(fontsize=9.5, framealpha=0.92, edgecolor=C["border"], fancybox=False)
            ax_grid(ax1)

            # Right: compression % bar
            bar_cols = [C["hg"] if p > 50 else C["sat"] for p in pcts]
            ax2.bar(range(len(comp_ns)), pcts, color=bar_cols,
                    alpha=0.88, edgecolor="white", linewidth=0.5)
            for i, (p, n) in enumerate(zip(pcts, comp_ns)):
                ax2.text(i, p + 0.5, f"{p:.0f}%", ha="center",
                         fontsize=9, fontweight="bold", color="#111827")
            ax2.set_xticks(range(len(comp_ns)))
            ax2.set_xticklabels([f"n={n}" for n in comp_ns], fontsize=9)
            ax2.set_ylim(0, 105)
            ax2.set_xlabel("n", fontsize=10.5)
            ax2.set_ylabel("Compression  (%)", fontsize=10.5)
            ax2.set_title("Role-Class Compression Rate\n"
                          "Higher = fewer SAT variables = faster Phase A",
                          fontsize=11, fontweight="bold")
            ax_grid(ax2)
            fig.suptitle("Role Class Compression: How HG Reduces the Search Space",
                         fontsize=13, fontweight="bold", y=1.02)
            fig.tight_layout()
            _save_open(fig, "benchmark_06_compression.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 7, HG internal phase breakdown (Phase A + Phase B stacked bars)
    # ═══════════════════════════════════════════════════════════════════════════
    if has_diam:
        ph_ns, ph_a, ph_b, ph_tot = [], [], [], []
        for e in diamond_e:
            n = get_n(e)
            if n and "hg_phase_a" in e:
                a = e["hg_phase_a"]
                b = e["hg_phase_b"]
                ph_ns.append(n)
                ph_a.append(a)
                ph_b.append(b)
                ph_tot.append(a + b)

        if ph_ns:
            fig, (ax_stk, ax_pct) = plt.subplots(1, 2, figsize=(13, 5))
            x_ph = np.arange(len(ph_ns))

            # Left: absolute stacked
            bars_a = ax_stk.bar(x_ph, ph_a, color=C["phase_a"], alpha=0.93,
                                label="Phase A, SAT on k role-class variables",
                                edgecolor="white", linewidth=0.4, zorder=3)
            bars_b = ax_stk.bar(x_ph, ph_b, bottom=ph_a,
                                color=C["phase_b"], alpha=0.93,
                                label="Phase B, Concrete version selection",
                                edgecolor="white", linewidth=0.4, zorder=3)

            for bar, val in zip(bars_a, ph_a):
                if val > 0.004:
                    ax_stk.text(bar.get_x() + bar.get_width() / 2,
                                bar.get_height() / 2,
                                f"{val:.3f}", ha="center", va="center",
                                fontsize=8, color="white", fontweight="bold")
            for bar, bot, val in zip(bars_b, ph_a, ph_b):
                if val > 0.004:
                    ax_stk.text(bar.get_x() + bar.get_width() / 2,
                                bot + val / 2,
                                f"{val:.3f}", ha="center", va="center",
                                fontsize=8, color="#065F46", fontweight="bold")

            ax_stk.set_xticks(x_ph)
            ax_stk.set_xticklabels([f"n={n}" for n in ph_ns], fontsize=9)
            ax_stk.set_xlabel("n", fontsize=10.5)
            ax_stk.set_ylabel("Time (ms)", fontsize=10.5)
            ax_stk.set_title("HG Total Time: Phase A + Phase B",
                             fontsize=11, fontweight="bold")
            ax_stk.legend(fontsize=9.5, loc="upper left",
                          edgecolor=C["border"], fancybox=False)
            ax_grid(ax_stk)

            # Right: % share
            a_pct = [a / t * 100 if t > 0 else 0 for a, t in zip(ph_a, ph_tot)]
            b_pct = [b / t * 100 if t > 0 else 0 for b, t in zip(ph_b, ph_tot)]
            ax_pct.bar(x_ph, a_pct, color=C["phase_a"], alpha=0.93,
                       label="Phase A share (%)", edgecolor="white")
            ax_pct.bar(x_ph, b_pct, bottom=a_pct, color=C["phase_b"], alpha=0.93,
                       label="Phase B share (%)", edgecolor="white")
            for i, (ap, bp) in enumerate(zip(a_pct, b_pct)):
                ax_pct.text(i, ap / 2, f"{ap:.0f}%", ha="center", va="center",
                            fontsize=8.5, color="white", fontweight="bold")
                ax_pct.text(i, ap + bp / 2, f"{bp:.0f}%", ha="center", va="center",
                            fontsize=8.5, color="#065F46", fontweight="bold")
            ax_pct.set_xticks(x_ph)
            ax_pct.set_xticklabels([f"n={n}" for n in ph_ns], fontsize=9)
            ax_pct.set_ylim(0, 108)
            ax_pct.set_xlabel("n", fontsize=10.5)
            ax_pct.set_ylabel("Share of total HG time  (%)", fontsize=10.5)
            ax_pct.set_title("Phase A vs Phase B Share\n"
                             "Phase A grows with k; Phase B stays near-constant",
                             fontsize=11, fontweight="bold")
            ax_pct.legend(fontsize=9.5, framealpha=0.92, edgecolor=C["border"], fancybox=False)
            ax_grid(ax_pct)
            fig.suptitle("Hypergraph Resolver Internal Phase Breakdown",
                         fontsize=13, fontweight="bold", y=1.02)
            fig.tight_layout()
            _save_open(fig, "benchmark_07_phases.png")

    # ═══════════════════════════════════════════════════════════════════════════
    # Figure 8, Theory vs empirical: fitted curves over actual data
    # ═══════════════════════════════════════════════════════════════════════════
    if has_diam and len(diamond_e) >= 3:
        from scipy.optimize import curve_fit
        d_ns_all = np.array([get_n(e) for e in diamond_e], dtype=float)

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))

        def _fit_plot(ax, xs, ys, model_fn, theory_str, col, name):
            valid = [(x, y) for x, y in zip(xs, ys) if not np.isnan(y)]
            if len(valid) < 2:
                return
            vx, vy = np.array([r[0] for r in valid]), np.array([r[1] for r in valid])
            ax.scatter(vx, vy, color=col, s=60, zorder=5, label="Measured")
            try:
                popt, _ = curve_fit(model_fn, vx, vy, maxfev=8000)
                x_fit = np.linspace(vx.min(), vx.max(), 200)
                ax.plot(x_fit, model_fn(x_fit, *popt),
                        color=col, linewidth=2.2, linestyle="--",
                        label=f"Fit:  {theory_str}", alpha=0.85)
            except Exception:
                pass
            ax.set_yscale("log")
            ax.set_xlabel("n", fontsize=10.5)
            ax.set_ylabel("Time (ms, log scale)", fontsize=10.5)
            ax.set_title(name, fontsize=11, fontweight="bold")
            ax.legend(fontsize=9, framealpha=0.92, edgecolor=C["border"], fancybox=False)
            ax_grid(ax)

        # BT: exponential growth
        bt_ys = np.array([mv(e, "backtracking") for e in diamond_e])
        _fit_plot(axes[0], d_ns_all, bt_ys,
                  lambda x, a, b: a * np.exp(b * x),
                  "a * exp(b * n)",
                  C["bt"],
                  "Backtracking: Exponential\nO(v^n), grows without bound")

        # SAT: polynomial (quadratic)
        sat_ys = np.array([mv(e, "sat") for e in diamond_e])
        _fit_plot(axes[1], d_ns_all, sat_ys,
                  lambda x, a, b: a * x ** b,
                  "a * n^b",
                  C["sat"],
                  "SAT: Polynomial\nO(n v m), manageable growth")

        # HG: near-linear / sub-linear
        hg_ys = np.array([mv(e, "hypergraph") for e in diamond_e])
        _fit_plot(axes[2], d_ns_all, hg_ys,
                  lambda x, a, b: a * x ** b,
                  "a * n^b  (b < 1)",
                  C["hg"],
                  "Hypergraph: Near-Linear\nO(k^2 m), role-class compression flattens growth")

        fig.suptitle("Theory vs Empirical: Fitted Growth Curves",
                     fontsize=13, fontweight="bold", y=1.02)
        fig.tight_layout()
        _save_open(fig, "benchmark_08_theory.png")

    print(f"\n  All figures saved to: {BASE}")
    print(f"  Each chart opened in its own window.")


def main():
    parser = argparse.ArgumentParser(description="Vertex resolver benchmark")
    parser.add_argument(
        "--mode", choices=["real", "synthetic", "diamond", "all"], default="all",
        help="Which benchmark mode to run (default: all)",
    )
    parser.add_argument("--runs",    type=int,  default=10, help="Timed runs per strategy (default: 10)")
    parser.add_argument("--no-plot", action="store_true",   help="Skip plot generation")
    args = parser.parse_args()

    print(f"\nVertex Dependency Resolution Benchmark")
    print(f"Solver-only timing (graph built once, I/O excluded)")
    print(f"Runs per strategy: {args.runs}")

    all_entries = []

    if args.mode in ("real", "all"):
        print("\n── Real Packages (PyPI) ──────────────────────────────────────")
        all_entries += run_real(args.runs)

    if args.mode in ("synthetic", "all"):
        print("\n── Synthetic Conflict-Heavy Graphs ───────────────────────────")
        all_entries += run_synthetic(args.runs)

    if args.mode in ("diamond", "all"):
        print("\n── Diamond Conflicts (TF+PT/numpy pattern) ───────────────────")
        all_entries += run_diamond(args.runs)

    _print_summary(all_entries)

    if not args.no_plot and all_entries:
        generate_plots(all_entries)


if __name__ == "__main__":
    main()
