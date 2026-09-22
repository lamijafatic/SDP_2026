"""
vertex test — run the full resolver benchmark and generate comparison plots.

Runs all three solvers (Hypergraph, SAT, Backtracking) across all scenario
categories, prints detailed per-scenario tables, a summary, and saves a
matplotlib PNG with three charts.
"""
import sys
import os

from core.ui import (
    banner, section, ok, warn, info, c,
    DIM, BOLD, BRIGHT_WHITE, BRIGHT_CYAN,
)


def run(args):
    banner()
    section("Resolver Benchmark")

    mode    = getattr(args, "mode",    "all")
    runs    = getattr(args, "runs",    10)
    no_plot = getattr(args, "no_plot", False)
    quick   = getattr(args, "quick",   False)

    if quick:
        mode = "diamond"
        runs = 5
        print(c("  Quick mode — diamond conflicts only, 5 runs per strategy.", DIM))
        print(c("  (Run without --quick for the full suite.)\n", DIM))
    else:
        print(c(f"  Mode: {mode}   ·   Runs per strategy: {runs}", DIM))
        print(c("  Solver-only timing: graph is built once before the timed loop.", DIM))
        print(c("  All timing uses time.perf_counter(); reported as median.\n", DIM))

    # benchmark.py lives at the project root
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)

    try:
        from benchmark import (
            run_real, run_synthetic, run_diamond,
            generate_plots, _print_summary,
        )
    except ImportError as e:
        print(warn(f"Could not import benchmark module: {e}"))
        return 1

    all_entries = []

    if mode in ("real", "all"):
        print(c("  ── Real PyPI scenarios (local cache — no network required) ──", BOLD))
        all_entries += run_real(runs)

    if mode in ("synthetic", "all"):
        print(c("  ── Synthetic chain scenarios ─────────────────────────────────", BOLD))
        all_entries += run_synthetic(runs)

    if mode in ("diamond", "all"):
        print(c("  ── Diamond conflict scenarios ────────────────────────────────", BOLD))
        print(c("  Note: Backtracking is skipped for n > 12 (>24 h projected).", DIM))
        all_entries += run_diamond(runs)

    if not all_entries:
        print(warn("No benchmark entries collected. Check --mode value."))
        return 1

    _print_summary(all_entries)

    if no_plot:
        print(c("  Plot skipped (--no-plot).", DIM))
    else:
        print(c("  Generating comparison plots (matplotlib)...", DIM))
        generate_plots(all_entries)

    print()
    print(ok("Benchmark complete."))
    if not no_plot:
        out = os.path.join(root, "benchmark_results.png")
        print(ok(f"Chart saved → {out}"))
    print()
    return 0
