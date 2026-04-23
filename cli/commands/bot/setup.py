import os
import re
from core.ui import section, ok, err, warn, info, c, DIM, bold, divider
from application.services.project_service import ProjectService
from infrastructure.git.git_client import GitClient
from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.toml.writer import save_config


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    section("Bot Setup")
    print(c("  This wizard will configure the automated PR bot.", DIM))
    print(c("  Your answers will be saved to mypm.toml - no manual editing needed.", DIM))
    print()

    git = GitClient()

    # ── Step 1: detect git repo and remote ──────────────────────────────────
    if not git.is_repo():
        print(err("This directory is not a git repository."))
        print(c("  Run 'git init && git remote add origin <url>' first.", DIM))
        return 1

    detected_repo = _detect_github_repo(git)
    if detected_repo:
        print(info(f"  Detected GitHub repo: {bold(detected_repo)}"))
    else:
        print(warn("  Could not auto-detect GitHub repo from remote URL."))

    print()

    # ── Step 2: github_repo ─────────────────────────────────────────────────
    repo_prompt = f"GitHub repo (owner/repo)"
    if detected_repo:
        repo_prompt += f" [{detected_repo}]"
    repo_prompt += ": "

    github_repo = input(f"  {repo_prompt}").strip()
    if not github_repo:
        github_repo = detected_repo or ""

    if not github_repo or "/" not in github_repo:
        print(err("  Invalid repo format. Expected: owner/repo"))
        return 1

    # ── Step 3: github token ────────────────────────────────────────────────
    print()
    env_token = os.environ.get("GITHUB_TOKEN", "")
    if env_token:
        print(ok(f"  GITHUB_TOKEN env var is already set."))
        store_token = input("  Store it in mypm.toml as well? [y/N]: ").strip().lower()
        if store_token == "y":
            github_token = env_token
        else:
            github_token = ""
    else:
        print(warn("  GITHUB_TOKEN env var is not set."))
        print(c("  You can paste your token here (stored in mypm.toml),", DIM))
        print(c("  or leave blank and set GITHUB_TOKEN env var later.", DIM))
        github_token = input("  GitHub token: ").strip()

    # ── Step 4: base branch ─────────────────────────────────────────────────
    print()
    default_branch = git.get_default_branch()
    base_input = input(f"  Base branch [{default_branch}]: ").strip()
    base_branch = base_input if base_input else default_branch

    # ── Step 5: update types ────────────────────────────────────────────────
    print()
    print(c("  Which update types should the bot process?", DIM))
    print(c("  patch = bug fixes (low risk), minor = new features (medium), major = breaking (high)", DIM))
    types_input = input("  Update types [patch, minor, major]: ").strip()
    if types_input:
        update_types = [t.strip() for t in types_input.split(",") if t.strip() in ("patch", "minor", "major")]
        if not update_types:
            print(warn("  Invalid input, using all types."))
            update_types = ["patch", "minor", "major"]
    else:
        update_types = ["patch", "minor", "major"]

    # ── Step 6: group updates ───────────────────────────────────────────────
    print()
    group_input = input("  Group all updates into a single PR? [y/N]: ").strip().lower()
    group_updates = group_input == "y"

    # ── Step 7: auto merge ──────────────────────────────────────────────────
    print()
    merge_input = input("  Enable auto-merge on created PRs? [y/N]: ").strip().lower()
    auto_merge = merge_input == "y"

    # ── Step 8: packages to ignore ─────────────────────────────────────────
    print()
    ignore_input = input("  Packages to ignore (comma-separated, or Enter to skip): ").strip()
    ignore = [p.strip() for p in ignore_input.split(",") if p.strip()] if ignore_input else []

    # ── Write to mypm.toml ──────────────────────────────────────────────────
    print()
    divider()

    config = load_config()
    config["bot"] = {
        "github_repo":   github_repo,
        "github_token":  github_token,
        "base_branch":   base_branch,
        "update_types":  update_types,
        "ignore":        ignore,
        "group_updates": group_updates,
        "auto_merge":    auto_merge,
        "labels":        True,
    }
    save_config(config)

    print()
    print(ok("  Bot configuration saved to mypm.toml."))
    print()
    print(c("  Next steps:", DIM))
    print(c("    arbor bot-check    preview available updates", DIM))
    print(c("    arbor bot-run      create GitHub PRs", DIM))
    print()
    return 0


def _detect_github_repo(git: GitClient):
    url = git.get_remote_url()
    if not url:
        return None
    m = re.search(r"github\.com[:/](.+?)/(.+?)(?:\.git)?$", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None
