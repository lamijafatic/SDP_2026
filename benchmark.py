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
        "label": "Small  — 3 direct deps (requests stack)",
        "deps": {
            "requests": ">=2.28.0",
            "numpy":    ">=1.24.0",
            "pandas":   ">=1.5.0",
        },
    },
    "medium": {
        "label": "Medium — 6 direct deps (data science stack)",
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
        "label": "Large  — 8 direct deps (ML stack)",
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
    {"label": "Synthetic S  — 5 pkgs × 5 versions, tight chain",           "n": 5,  "v": 5,  "c": 0},
    {"label": "Synthetic M  — 10 pkgs × 8 versions, tight chain",          "n": 10, "v": 8,  "c": 0},
    {"label": "Synthetic L  — 15 pkgs × 10 versions, tight chain",         "n": 15, "v": 10, "c": 0},
    {"label": "Synthetic LC — 15 pkgs × 10 versions, chain + 5 conflicts", "n": 15, "v": 10, "c": 5},
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
    {"label": "Diamond S  — 3+3 frameworks + core",   "n": 3},
    {"label": "Diamond M  — 5+5 frameworks + core",   "n": 5},
    {"label": "Diamond L  — 8+8 frameworks + core",   "n": 8},
    {"label": "Diamond XL — 10+10 frameworks + core", "n": 10},
    {"label": "Diamond XXL— 12+12 frameworks + core", "n": 12},
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
        if data["failed"] or not data["times"]:
            print(f"  {strategy:<14} {'FAILED':>10}")
            continue
        t = data["times"]
        mn, med, mx = min(t), _median(t), max(t)
        print(f"  {strategy:<14} {_fmt(mn):>10} {_fmt(med):>10} {_fmt(mx):>10}  {_bar(med, max_med)}")
    print(f"{'═' * 66}")


def _print_summary(all_entries: list):
    print(f"\n{'═' * 66}")
    print("  SUMMARY — Median solver-only times")
    print(f"{'─' * 66}")
    print(f"  {'Scenario':<36}  {'SAT':>9}  {'BT':>9}  {'HG':>9}  Fastest")
    print(f"  {'-'*36}  {'-'*9}  {'-'*9}  {'-'*9}  {'-'*11}")
    for entry in all_entries:
        name, results = entry["name"], entry["results"]
        row = {
            s: (_median(d["times"]) if not d["failed"] and d["times"] else float("inf"))
            for s, d in results.items()
        }
        fastest = min(row, key=row.get)
        print(
            f"  {name[:36]:<36}  "
            f"{_fmt(row['sat']):>9}  "
            f"{_fmt(row['backtracking']):>9}  "
            f"{_fmt(row['hypergraph']):>9}  "
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


def run_diamond(runs: int) -> list:
    entries = []
    for case in DIAMOND_CASES:
        n         = case["n"]
        graph     = DiamondConflictGraph(n)
        pkg_count = 2 * n + 1
        results   = {
            "sat":          _time_solver(SATResolver, graph, runs),
            "backtracking": _time_solver(BacktrackingResolver, graph, runs),
            "hypergraph":   _time_hypergraph_synthetic(graph, runs),
        }
        _print_table(case["label"], pkg_count, runs, results)
        entries.append({"name": case["label"][:36], "results": results})
    return entries


def generate_plots(all_entries: list):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import matplotlib.ticker as ticker
        import numpy as np
    except ImportError:
        print("  [plots skipped — pip install matplotlib]\n")
        return

    C = {
        "sat":          "#4472C4",
        "backtracking": "#ED7D31",
        "hypergraph":   "#55A868",
    }
    LBL = {"sat": "SAT", "backtracking": "Backtracking", "hypergraph": "Hypergraph"}

    def med(entry, s):
        d = entry["results"][s]
        return statistics.median(d["times"]) if not d["failed"] and d["times"] else None

    def short(name):
        table = {
            "small":  "Real-S\n(8 pkg)",
            "medium": "Real-M\n(12 pkg)",
            "large":  "Real-L\n(13 pkg)",
        }
        if name in table:
            return table[name]
        if "Synthetic S"  in name: return "Chain-S\n5p×5v"
        if "Synthetic M"  in name: return "Chain-M\n10p×8v"
        if "Synthetic L " in name: return "Chain-L\n15p×10v"
        if "Synthetic LC" in name: return "Chain-LC\n+5 CF"
        if "3+3"   in name: return "Diam-S\nn=3"
        if "5+5"   in name: return "Diam-M\nn=5"
        if "8+8"   in name: return "Diam-L\nn=8"
        if "10+10" in name: return "Diam-XL\nn=10"
        if "12+12" in name: return "Diam-XXL\nn=12"
        return name[:10]

    real_e    = [e for e in all_entries if e["name"] in ("small", "medium", "large")]
    synth_e   = [e for e in all_entries if "Synthetic" in e["name"]]
    diamond_e = [e for e in all_entries if "Diamond"   in e["name"]]

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("ggplot")

    fig = plt.figure(figsize=(22, 14))
    fig.patch.set_facecolor("#F7F9FC")
    gs = gridspec.GridSpec(
        2, 2, figure=fig,
        hspace=0.55, wspace=0.30,
        left=0.055, right=0.975, top=0.905, bottom=0.07,
    )
    ax_all   = fig.add_subplot(gs[0, :])
    ax_scale = fig.add_subplot(gs[1, 0])
    ax_speed = fig.add_subplot(gs[1, 1])

    groups = [(g, e) for g, e in [
        ("Stvarni PyPI paketi",  real_e),
        ("Sintetički lanci",     synth_e),
        ("Diamond konflikti",    diamond_e),
    ] if e]

    ordered_entries = [e for _, grp in groups for e in grp]

    x_pos   = []
    x_lbls  = []
    spans   = []
    cursor  = 0.0
    for gname, grp in groups:
        start = cursor
        for e in grp:
            x_pos.append(cursor)
            x_lbls.append(short(e["name"]))
            cursor += 1.0
        spans.append((start, cursor - 1.0, gname))
        cursor += 0.5

    x     = np.array(x_pos)
    width = 0.27
    off   = {"sat": -width, "backtracking": 0.0, "hypergraph": width}

    for s in STRATEGIES:
        vals = [max(med(e, s) or 0.001, 0.001) for e in ordered_entries]
        ax_all.bar(
            x + off[s], vals, width,
            label=LBL[s], color=C[s], alpha=0.88,
            edgecolor="white", linewidth=0.5, zorder=3,
        )

    ax_all.set_yscale("log")
    ax_all.set_ylabel("Vrijeme rješavanja (ms)  —  log skala", fontsize=11)
    ax_all.set_title(
        "Svi scenariji — poređenje solvera   (niže = brže,  log skala)",
        fontsize=13, fontweight="bold", pad=11,
    )
    ax_all.set_xticks(x)
    ax_all.set_xticklabels(x_lbls, fontsize=8.5, ha="center", linespacing=1.3)
    ax_all.legend(loc="upper left", fontsize=10, framealpha=0.92)
    ax_all.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.4g} ms"))
    ax_all.set_axisbelow(True)
    ax_all.grid(axis="y", alpha=0.35, linewidth=0.7)

    for start, end, gname in spans:
        mid_x = (start + end) / 2
        ax_all.text(
            mid_x, 1.07, gname,
            transform=ax_all.get_xaxis_transform(),
            ha="center", va="bottom", clip_on=False,
            fontsize=10.5, fontweight="bold", color="#2C2C2C",
            bbox=dict(
                boxstyle="round,pad=0.25",
                facecolor="#E4EAF5", edgecolor="#9AAAC8",
                linewidth=0.9, alpha=0.95,
            ),
        )
        if start > 0:
            ax_all.axvline(
                start - 0.38, color="#BBBBBB",
                linestyle="--", linewidth=1.1, alpha=0.65, zorder=1,
            )

    if diamond_e:
        d_ns = []
        for e in diamond_e:
            n = e["name"]
            if "3+3"   in n: d_ns.append(3)
            elif "5+5"  in n: d_ns.append(5)
            elif "8+8"  in n: d_ns.append(8)
            elif "10+10" in n: d_ns.append(10)
            elif "12+12" in n: d_ns.append(12)
            else: d_ns.append(len(d_ns) + 1)

        for s in STRATEGIES:
            vals = [med(e, s) for e in diamond_e]
            ax_scale.plot(
                d_ns, vals,
                marker="o", linewidth=2.6, markersize=8,
                color=C[s], label=LBL[s], zorder=3,
            )
            last = vals[-1]
            if last:
                ax_scale.annotate(
                    _fmt(last),
                    xy=(d_ns[-1], last),
                    xytext=(7, 2), textcoords="offset points",
                    fontsize=8.5, color=C[s], fontweight="bold",
                )

        ax_scale.set_yscale("log")
        ax_scale.axhline(
            1000, color="#CC2222", linestyle=":", linewidth=1.6,
            alpha=0.75, zorder=2, label="1 sekunda",
        )
        ax_scale.axhline(
            1, color="#999999", linestyle=":", linewidth=1.0,
            alpha=0.5, zorder=2, label="1 ms",
        )
        ax_scale.set_xticks(d_ns)
        ax_scale.set_xticklabels([f"n={n}" for n in d_ns], fontsize=10)
        ax_scale.set_xlabel("Broj parova frameworka  (n+n + 1 zajednički core)", fontsize=10)
        ax_scale.set_ylabel("Vrijeme (ms) — log skala", fontsize=10)
        ax_scale.set_title(
            "Diamond skaliranje — BT raste eksponencijalno, HG ostaje flat",
            fontsize=11.5, fontweight="bold",
        )
        ax_scale.legend(fontsize=9.5, loc="upper left")
        ax_scale.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.4g} ms"))
        ax_scale.set_axisbelow(True)
        ax_scale.grid(axis="y", alpha=0.35, linewidth=0.7)

    spd_lbls   = []
    bt_ratios  = []
    sat_ratios = []
    for e in all_entries:
        hg  = med(e, "hypergraph")
        bt  = med(e, "backtracking")
        sat = med(e, "sat")
        if hg and hg > 0 and bt and sat:
            spd_lbls.append(short(e["name"]).replace("\n", " "))
            bt_ratios.append(bt / hg)
            sat_ratios.append(sat / hg)

    y = np.arange(len(spd_lbls))
    h = 0.34

    ax_speed.barh(
        y + h / 2, bt_ratios, h,
        color=[C["backtracking"] if v >= 1 else "#F5C89A" for v in bt_ratios],
        alpha=0.87, edgecolor="white", linewidth=0.4, label="BT / HG",
    )
    ax_speed.barh(
        y - h / 2, sat_ratios, h,
        color=[C["sat"] if v >= 1 else "#AABCE0" for v in sat_ratios],
        alpha=0.87, edgecolor="white", linewidth=0.4, label="SAT / HG",
    )
    ax_speed.axvline(
        1.0, color="#1A1A1A", linewidth=2.0,
        linestyle="--", zorder=5, label="Jednako (1×)",
    )
    ax_speed.set_xscale("log")
    ax_speed.set_yticks(y)
    ax_speed.set_yticklabels(spd_lbls, fontsize=8.5)
    ax_speed.set_xlabel(
        "Ratio vs Hypergraph   (>1 = HG brži,  <1 = HG sporiji,  log skala)",
        fontsize=10,
    )
    ax_speed.set_title(
        "Ubrzanje Hypergraph-a naspram BT i SAT",
        fontsize=11.5, fontweight="bold",
    )
    ax_speed.legend(fontsize=9.5, loc="lower right")
    ax_speed.xaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.3g}×"))
    ax_speed.set_axisbelow(True)
    ax_speed.grid(axis="x", alpha=0.35, linewidth=0.7)

    for i, bv in enumerate(bt_ratios):
        if bv >= 5:
            ax_speed.text(
                bv * 1.08, i + h / 2, f"{bv:.0f}×",
                va="center", fontsize=7.5, color="#333333", fontweight="bold",
            )

    fig.suptitle(
        "Arbor Dependency Resolver  —  Benchmark Analiza",
        fontsize=15, fontweight="bold", y=0.975,
    )

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.png")
    plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"\n  Graf sačuvan → {out}")
    try:
        subprocess.run(["open", out], check=False)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Arbor resolver benchmark")
    parser.add_argument(
        "--mode", choices=["real", "synthetic", "diamond", "all"], default="all",
        help="Which benchmark mode to run (default: all)",
    )
    parser.add_argument("--runs",    type=int,  default=10, help="Timed runs per strategy (default: 10)")
    parser.add_argument("--no-plot", action="store_true",   help="Skip plot generation")
    args = parser.parse_args()

    print(f"\nArbor Dependency Resolution Benchmark")
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
