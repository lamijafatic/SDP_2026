"""
ReportService, after a successful `vertex resolve --report`, pops up
three native matplotlib windows on screen (not a browser page):

  1. Speed, SAT vs Backtracking vs Hypergraph, timed on this project
  2. Phase split, Phase A (SAT over role classes) vs Phase B (version pick)
  3. Complexity, theoretical O(v^n) backtracking vs O(n^2) hypergraph,
                   with this project's own n marked on the curve

Designed for a live screen-recorded demo: everything renders locally,
no browser, no network.
"""
import signal
import statistics
import time

import matplotlib.pyplot as plt


class _Timeout(Exception):
    pass


def _with_timeout(fn, seconds):
    def _handler(signum, frame):
        raise _Timeout()
    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    t0 = time.perf_counter()
    try:
        result = fn()
        dt = (time.perf_counter() - t0) * 1000
        return result, dt
    except _Timeout:
        return None, None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


class ReportService:
    BT_TIMEOUT_S = 4

    def generate(self, graph, solution, direct_deps, strategy_used, elapsed_ms,
                 runs=5, **_ignored):
        """Build and display the 3 demo charts as native windows."""
        from domain.resolver.sat_resolver import SATResolver
        from domain.resolver.backtracking_resolver import BacktrackingResolver
        from domain.resolver.hypergraph_resolver import HypergraphResolver
        from model_math_trans import (
            build_hypergraph, compute_role_classes, build_role_graph,
            phase_a_solve, phase_b_select,
        )

        n_packages = len(graph.dependencies)

        # ── 1. solver timing (median of `runs`) ──────────────────────────────
        timings = {}
        for label, cls in [("SAT", SATResolver), ("Backtracking", BacktrackingResolver),
                            ("Hypergraph", HypergraphResolver)]:
            samples = []
            timeout = self.BT_TIMEOUT_S if label == "Backtracking" else 15
            for _ in range(runs):
                _, ms = _with_timeout(lambda cls=cls: cls(graph).solve(), timeout)
                if ms is None:
                    samples = None
                    break
                samples.append(ms)
            timings[label] = statistics.median(samples) if samples else None

        # ── 2. Phase A / Phase B split (median of `runs`) ────────────────────
        H = build_hypergraph(graph, graph.repo)
        role_classes = compute_role_classes(H)
        role_deps, role_conflicts = build_role_graph(H, role_classes)
        required = set(graph.dependencies.keys())

        a_times, b_times = [], []
        for _ in range(runs):
            t0 = time.perf_counter()
            selected = phase_a_solve(role_classes, role_deps, role_conflicts, required, set())
            a_times.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            if selected is not None:
                phase_b_select(H, selected, role_classes, graph)
            b_times.append((time.perf_counter() - t0) * 1000)

        phase_a_ms = statistics.median(a_times)
        phase_b_ms = statistics.median(b_times)

        n_versions = sum(len(graph.get_candidates(p)) for p in graph.dependencies)
        k_roles = len(role_classes)

        self._fig_speed(timings, n_packages)
        self._fig_phase_split(phase_a_ms, phase_b_ms, n_versions, k_roles)
        self._fig_complexity(n_packages, n_versions, k_roles)

        plt.show()

    # ── Chart 1: solver speed comparison ─────────────────────────────────────
    def _fig_speed(self, timings, n_packages):
        palette = {"SAT": "#3B6EA5", "Backtracking": "#B5533C", "Hypergraph": "#2F8F5B"}
        labels, values, colors = [], [], []
        for label in ["SAT", "Backtracking", "Hypergraph"]:
            ms = timings.get(label)
            labels.append(label if ms is not None else f"{label}\n(>4s, skipped)")
            values.append(ms if ms is not None else 0)
            colors.append(palette[label])

        fig, ax = plt.subplots(figsize=(6.2, 4.4), num="1. Speed")
        bars = ax.bar(labels, values, color=colors, width=0.55, zorder=3,
                       edgecolor="black", linewidth=0.6)
        for bar, ms in zip(bars, values):
            if ms > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                        f"{ms:.2f} ms", ha="center", va="bottom", fontsize=9.5,
                        fontweight="bold")
        ax.set_ylabel("Resolution time (ms, median)", fontsize=10)
        ax.set_title(f"Solver speed, {n_packages} packages in this project",
                     fontsize=11, fontweight="bold")
        ax.grid(axis="y", color="#dddddd", linewidth=0.7, zorder=0)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        fig.tight_layout()

    # ── Chart 2: Phase A vs Phase B time split ───────────────────────────────
    def _fig_phase_split(self, phase_a_ms, phase_b_ms, n_versions, k_roles):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.2), num="2. Phase split")

        labels = ["Phase A\n(SAT over role classes)", "Phase B\n(version selection)"]
        values = [phase_a_ms, phase_b_ms]
        colors = ["#5AB4E8", "#F2AF4A"]
        bars = ax1.bar(labels, values, color=colors, edgecolor="black",
                        linewidth=0.6, width=0.55, zorder=3)
        for bar, v in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.02,
                      f"{v:.3f} ms", ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax1.set_ylabel("Time (ms, median)", fontsize=10)
        ax1.set_title("Time per phase", fontsize=10.5, fontweight="bold")
        ax1.grid(axis="y", color="#dddddd", linewidth=0.7, zorder=0)
        for spine in ["top", "right"]:
            ax1.spines[spine].set_visible(False)

        total = phase_a_ms + phase_b_ms
        pct = [phase_a_ms / total * 100 if total else 0, phase_b_ms / total * 100 if total else 0]
        ax2.pie(pct, labels=[f"Phase A\n{pct[0]:.0f}%", f"Phase B\n{pct[1]:.0f}%"],
                colors=colors, autopct=None, startangle=90,
                wedgeprops=dict(edgecolor="white", linewidth=1.5))
        ax2.set_title(f"Role-class compression: |V|={n_versions} → k={k_roles}",
                      fontsize=10.5, fontweight="bold")

        fig.tight_layout()

    # ── Chart 3: theoretical complexity ──────────────────────────────────────
    def _fig_complexity(self, n_packages, n_versions, k_roles):
        import numpy as np

        n_max = max(30, n_packages + 5)
        n_range = np.arange(1, n_max + 1)
        v = max(2, round(n_versions / max(n_packages, 1)))

        bt_curve = v ** n_range.astype(float)
        hg_curve = n_range.astype(float) ** 2

        fig, ax = plt.subplots(figsize=(7, 4.6), num="3. Complexity")
        ax.plot(n_range, bt_curve, color="#B5533C", lw=2, label=f"Naive backtracking, O(v$^n$), v≈{v}")
        ax.plot(n_range, hg_curve, color="#2F8F5B", lw=2, label="Hypergraph, O(n²)")
        ax.set_yscale("log")

        ax.axvline(n_packages, color="#555", lw=1, ls="--")
        ax.scatter([n_packages], [n_packages ** 2], color="#2F8F5B", zorder=5, s=45,
                   edgecolor="black", linewidth=0.6)
        ax.annotate(f"this project\nn = {n_packages}",
                    xy=(n_packages, n_packages ** 2), xytext=(8, 12),
                    textcoords="offset points", fontsize=8.5, fontweight="bold")

        ax.set_xlabel("n  (number of packages)", fontsize=10)
        ax.set_ylabel("operations (log scale)", fontsize=10)
        ax.set_title("Worst-case growth: backtracking vs hypergraph resolver",
                     fontsize=11, fontweight="bold")
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(True, which="both", color="#e5e5e5", linewidth=0.6)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        fig.tight_layout()
