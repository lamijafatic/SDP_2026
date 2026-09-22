import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        prog="vertex",
        description="Vertex — Python Package Manager with Hypergraph Dependency Resolution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  vertex init                    Initialize a new project\n"
            "  vertex add numpy '>=1.20'      Add a dependency\n"
            "  vertex resolve                 Resolve all dependencies\n"
            "  vertex install                 Install resolved packages\n"
            "  vertex search sci              Search available packages\n"
            "  vertex versions numpy          Show available versions\n"
        ),
    )
    parser.add_argument(
        "--version", action="version", version="vertex 0.1.0"
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── Project ──────────────────────────────────────────────
    p_init = sub.add_parser("init", help="Initialize a new project")
    p_init.add_argument("name", nargs="?", default=None, help="Project name")
    p_init.add_argument("--python", default=None, help="Python version (e.g. 3.11)")

    sub.add_parser("info", help="Show project information")

    sub.add_parser("status", help="Show full project and environment status")

    sub.add_parser("doctor", help="Run a health check on the project")

    p_import = sub.add_parser(
        "import",
        help="Import dependencies from an existing project (requirements.txt, pyproject.toml, etc.)",
    )
    p_import.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to project directory (default: current directory)",
    )

    # ── Dependency ───────────────────────────────────────────
    p_add = sub.add_parser("add", help="Add a dependency")
    p_add.add_argument("package", help="Package name")
    p_add.add_argument("constraint", nargs="?", default=">=0.1", help="Version constraint (e.g. '>=1.20')")

    p_remove = sub.add_parser("remove", help="Remove a dependency")
    p_remove.add_argument("package", help="Package name to remove")

    sub.add_parser("show", help="List all declared dependencies")

    p_update = sub.add_parser("update", help="Update a dependency to latest compatible version")
    p_update.add_argument("package", nargs="?", default=None, help="Package to update (omit for all)")

    # ── Resolution ───────────────────────────────────────────
    p_resolve = sub.add_parser("resolve", help="Resolve dependencies (default: hypergraph solver)")
    p_resolve.add_argument(
        "--strategy",
        choices=["hypergraph", "sat", "backtracking"],
        default="hypergraph",
        help="Resolution algorithm (default: hypergraph)",
    )
    p_resolve.add_argument(
        "--report",
        action="store_true",
        help="Generate an HTML report (dependency graph + solver comparison) and open it",
    )

    sub.add_parser("lock", help="Regenerate lock file (same as resolve)")

    sub.add_parser("explain", help="Explain why each version was selected")

    sub.add_parser("conflicts", help="Show known package conflicts in the registry")

    # ── Environment ──────────────────────────────────────────
    p_install = sub.add_parser("install", help="Install packages from lock file into venv")
    p_install.add_argument(
        "--dry-run", action="store_true", help="Show what would be installed without doing it"
    )

    sub.add_parser("sync", help="Sync virtual environment with current lock file")

    sub.add_parser("clean", help="Remove the virtual environment")

    sub.add_parser("build", help="Build a distribution package (sdist + wheel)")

    # ── Package Registry ─────────────────────────────────────
    p_search = sub.add_parser("search", help="Search available packages")
    p_search.add_argument("query", help="Search query")

    p_versions = sub.add_parser("versions", help="Show available versions for a package")
    p_versions.add_argument("package", help="Package name")

    sub.add_parser("list", help="List all packages in the registry")

    # ── Analysis ─────────────────────────────────────────────
    p_test = sub.add_parser(
        "test",
        help="Full resolver benchmark — all scenarios, detailed tables, and comparison plots",
    )
    p_test.add_argument(
        "--mode",
        choices=["real", "synthetic", "diamond", "all"],
        default="all",
        help="Which scenario group to run (default: all)",
    )
    p_test.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Timed runs per strategy per scenario (default: 10)",
    )
    p_test.add_argument(
        "--quick",
        action="store_true",
        help="Diamond conflicts only, 5 runs — fastest meaningful comparison",
    )
    p_test.add_argument(
        "--no-plot",
        action="store_true",
        dest="no_plot",
        help="Skip matplotlib chart generation",
    )

    sub.add_parser(
        "stat",
        help="Live algorithm efficiency benchmark — bar charts, speedups, complexity",
    )

    p_demo = sub.add_parser(
        "demo",
        help="Interactive algorithm walkthrough — step through a diamond conflict example",
    )
    p_demo.add_argument(
        "--auto",
        action="store_true",
        help="Run all steps without pausing (non-interactive mode)",
    )

    # ── Debug ────────────────────────────────────────────────
    sub.add_parser("graph", help="Visualize the dependency graph")

    sub.add_parser("trace", help="Trace the hypergraph resolution process step-by-step")

    sub.add_parser("dump", help="Dump internal project state as JSON")

    # ── Bot ──────────────────────────────────────────────────
    sub.add_parser(
        "bot-setup",
        help="Interactive wizard to configure the PR bot (start here)",
    )

    sub.add_parser(
        "bot-check",
        help="Check for available dependency updates (no PRs created)",
    )

    p_bot_run = sub.add_parser(
        "bot-run",
        help="Create GitHub PRs for dependency updates",
    )
    p_bot_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without pushing or creating PRs",
    )

    p_bot_cfg = sub.add_parser(
        "bot-config",
        help="Show or initialise bot configuration in mypm.toml",
    )
    p_bot_cfg.add_argument(
        "--init",
        action="store_true",
        help="Add default [bot] section to mypm.toml if not present",
    )
    p_bot_cfg.add_argument(
        "--show",
        action="store_true",
        help="Show current bot configuration (default behaviour)",
    )

    return parser.parse_args()
