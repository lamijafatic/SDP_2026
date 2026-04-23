import os
from core.ui import section, ok, warn, info, table, c, DIM, bold
from application.services.project_service import ProjectService
from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.toml.writer import save_config


_DEFAULTS = {
    "github_token": "",
    "github_repo": "",
    "base_branch": "main",
    "update_types": ["patch", "minor", "major"],
    "ignore": [],
    "group_updates": False,
    "auto_merge": False,
    "labels": True,
}

_DESCRIPTIONS = {
    "github_token":  "GitHub personal access token (or use GITHUB_TOKEN env var)",
    "github_repo":   "Target repo as 'owner/repo' (auto-detected from git remote if blank)",
    "base_branch":   "Branch PRs target (default: main)",
    "update_types":  "Which update types to process: patch, minor, major",
    "ignore":        "Packages to skip (list of names)",
    "group_updates": "Group all updates into a single PR instead of one per package",
    "auto_merge":    "Enable auto-merge on created PRs (requires branch protection rules)",
    "labels":        "Add type/risk labels to PRs",
}


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    show_only = getattr(args, "show", False)
    init_bot = getattr(args, "init", False)

    if show_only or (not init_bot):
        _show_config()
        return 0

    if init_bot:
        _init_config()
        return 0

    _show_config()
    return 0


def _show_config():
    section("Bot Configuration")
    config = load_config()
    bot = config.get("bot", {})

    if not bot:
        print(warn("  No [bot] section found in mypm.toml."))
        print(c("  Run 'arbor bot-config --init' to add default configuration.", DIM))
        print()
        return

    rows = []
    for key, default in _DEFAULTS.items():
        raw = bot.get(key, default)
        # Mask token
        if key == "github_token":
            val = "*** (set)" if raw else c("(not set – uses GITHUB_TOKEN env var)", DIM)
        else:
            val = str(raw) if not isinstance(raw, list) else ", ".join(str(x) for x in raw)
        desc = _DESCRIPTIONS.get(key, "")
        rows.append([bold(key), val, c(desc, DIM)])

    table(["Key", "Value", "Description"], rows)

    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        print(ok("  GITHUB_TOKEN env var is set."))
    else:
        print(warn("  GITHUB_TOKEN env var is not set."))
    print()


def _init_config():
    section("Initialising Bot Configuration")
    config = load_config()

    if "bot" in config:
        print(info("  [bot] section already exists in mypm.toml – merging defaults."))

    bot = config.setdefault("bot", {})
    added = []
    for key, default in _DEFAULTS.items():
        if key not in bot:
            bot[key] = default
            added.append(key)

    save_config(config)

    if added:
        print(ok(f"  Added default values for: {', '.join(added)}"))
    else:
        print(ok("  [bot] section is already fully configured."))

    print()
    print(c("  Edit mypm.toml to customise the bot settings.", DIM))
    print(c("  Set GITHUB_TOKEN env var or fill in 'github_token' before running 'arbor bot-run'.", DIM))
