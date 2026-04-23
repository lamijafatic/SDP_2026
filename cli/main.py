import sys
import traceback

from cli.parser import parse_args

# Project commands
from cli.commands.project.init import run as init_cmd
from cli.commands.project.info import run as info_cmd
from cli.commands.project.doctor import run as doctor_cmd
from cli.commands.project.status import run as status_cmd
from cli.commands.project.import_cmd import run as import_cmd

# Dependency commands
from cli.commands.dependency.add import run as add_cmd
from cli.commands.dependency.remove import run as remove_cmd
from cli.commands.dependency.show import run as show_cmd
from cli.commands.dependency.update import run as update_cmd

# Resolution commands
from cli.commands.resolution.resolve import run as resolve_cmd
from cli.commands.resolution.lock import run as lock_cmd
from cli.commands.resolution.explain import run as explain_cmd
from cli.commands.resolution.conflicts import run as conflicts_cmd

# Environment commands
from cli.commands.environment.install import run as install_cmd
from cli.commands.environment.sync import run as sync_cmd
from cli.commands.environment.clean import run as clean_cmd
from cli.commands.environment.build import run as build_cmd

# Package registry commands
from cli.commands.package.search import run as search_cmd
from cli.commands.package.versions import run as versions_cmd
from cli.commands.package.list_pkgs import run as list_cmd

# Debug commands
from cli.commands.debug.graph import run as graph_cmd
from cli.commands.debug.trace import run as trace_cmd
from cli.commands.debug.dump import run as dump_cmd

# Bot commands
from cli.commands.bot.setup import run as bot_setup_cmd
from cli.commands.bot.check import run as bot_check_cmd
from cli.commands.bot.run import run as bot_run_cmd
from cli.commands.bot.config_cmd import run as bot_config_cmd


COMMANDS = {
    # project
    "init": init_cmd,
    "info": info_cmd,
    "doctor": doctor_cmd,
    "status": status_cmd,
    "import": import_cmd,
    # dependency
    "add": add_cmd,
    "remove": remove_cmd,
    "show": show_cmd,
    "update": update_cmd,
    # resolution
    "resolve": resolve_cmd,
    "lock": lock_cmd,
    "explain": explain_cmd,
    "conflicts": conflicts_cmd,
    # environment
    "install": install_cmd,
    "sync": sync_cmd,
    "clean": clean_cmd,
    "build": build_cmd,
    # package registry
    "search": search_cmd,
    "versions": versions_cmd,
    "list": list_cmd,
    # debug
    "graph": graph_cmd,
    "trace": trace_cmd,
    "dump": dump_cmd,
    # bot
    "bot-setup": bot_setup_cmd,
    "bot-check": bot_check_cmd,
    "bot-run": bot_run_cmd,
    "bot-config": bot_config_cmd,
}


def main():
    try:
        args = parse_args()

        if not args.command:
            from core.ui import banner, c, DIM, info
            banner()
            print(c("  Usage: arbor <command> [options]", DIM))
            print()
            print(c("  Project:      init, info, status, doctor, import", DIM))
            print(c("  Dependencies: add, remove, show, update", DIM))
            print(c("  Resolution:   resolve, lock, explain, conflicts", DIM))
            print(c("  Environment:  install, sync, clean, build", DIM))
            print(c("  Registry:     search, versions, list", DIM))
            print(c("  Debug:        graph, trace, dump", DIM))
            print(c("  Bot:          bot-setup, bot-check, bot-run, bot-config", DIM))
            print()
            print(c("  Run 'arbor --help' for full documentation.", DIM))
            return 0

        handler = COMMANDS.get(args.command)
        if not handler:
            from core.ui import err
            print(err(f"Unknown command: '{args.command}'"))
            print(f"  Run 'arbor --help' to see available commands.")
            return 1

        return handler(args) or 0

    except KeyboardInterrupt:
        print()
        from core.ui import warn
        print(warn("Interrupted by user."))
        return 130

    except Exception as e:
        from core.ui import err, c, DIM
        print(err(f"Unexpected error: {e}"))
        if "--debug" in sys.argv or "-v" in sys.argv:
            traceback.print_exc()
        else:
            print(c("  Run with --debug for full traceback.", DIM))
        return 1


if __name__ == "__main__":
    sys.exit(main())
