import os
from core.ui import section, ok, err, warn, info, table, c, DIM, Spinner, bold, divider
from application.services.project_service import ProjectService
from application.services.pr_bot_service import PRBotService, PRBotError
from infrastructure.git.git_client import GitClient
from infrastructure.persistence.toml.reader import load_config


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    if not _check_prerequisites():
        return 1

    dry_run = getattr(args, "dry_run", False)

    if dry_run:
        section("Bot Dry Run - No PRs will be created")
    else:
        section("Running Dependency Update Bot")

    def on_progress(msg: str):
        print(info(f"  {msg}"))

    sp = Spinner("Checking for updates...")
    sp.start()
    try:
        bot_svc = PRBotService()
        updates_preview = bot_svc.check_updates()
        sp.stop(success=True, msg=f"{len(updates_preview)} update(s) found")
    except Exception as e:
        sp.stop(success=False, msg=str(e))
        return 1

    if not updates_preview:
        print(ok("All dependencies are up to date. Nothing to do."))
        return 0

    print()
    for u in updates_preview:
        print(info(
            f"  {bold(u.package)}: {u.current_version} -> {u.latest_version}"
            f"  [{u.update_type} / {u.risk_level} risk]"
        ))
    print()

    if not dry_run:
        sp2 = Spinner("Creating branches and PRs...")
        sp2.start()
        try:
            results = bot_svc.run(dry_run=False, on_progress=on_progress)
            sp2.stop(success=True, msg="Done")
        except PRBotError as e:
            sp2.stop(success=False, msg="Bot error")
            print(err(str(e)))
            return 1
        except Exception as e:
            sp2.stop(success=False, msg=str(e))
            return 1
    else:
        results = bot_svc.run(dry_run=True)

    print()
    _print_results(results, dry_run)
    return 0


def _check_prerequisites() -> bool:
    issues = []

    # Git repo check
    git = GitClient()
    if not git.is_repo():
        issues.append("Not a git repository. Run 'git init' first.")
    else:
        if not git.get_remote_url():
            issues.append("No git remote found. Run 'git remote add origin <url>' first.")

    # Lock file check
    if not os.path.exists("mypm.lock"):
        issues.append("No lock file found. Run 'arbor resolve' first.")

    # Bot config check
    try:
        config = load_config()
        bot = config.get("bot", {})
        if not bot:
            issues.append("No [bot] section in mypm.toml. Run 'arbor bot-setup' first.")
        else:
            token = bot.get("github_token") or os.environ.get("GITHUB_TOKEN", "")
            if not token:
                issues.append(
                    "GitHub token not set. Run 'arbor bot-setup' or set GITHUB_TOKEN env var."
                )
            if not bot.get("github_repo"):
                issues.append(
                    "github_repo not configured. Run 'arbor bot-setup'."
                )
    except Exception:
        issues.append("Could not read mypm.toml. Run 'arbor bot-setup' first.")

    if issues:
        print()
        print(err("Cannot run bot - setup incomplete:"))
        for issue in issues:
            print(c(f"  - {issue}", DIM))
        print()
        print(c("  Run 'arbor bot-setup' to configure everything.", DIM))
        print()
        return False

    return True


def _print_results(results, dry_run: bool):
    if not results:
        return

    rows = []
    for r in results:
        updates = r.get("updates") or ([r["update"]] if "update" in r else [])
        pkg = ", ".join(u.package for u in updates) if updates else "?"
        status = r.get("status", "?")
        pr_url = r.get("pr_url") or ("(dry run)" if dry_run else "-")
        err_msg = r.get("error", "")
        rows.append([pkg, status, pr_url or err_msg])

    table(["Package(s)", "Status", "PR / Note"], rows)
    print()

    created = sum(1 for r in results if r.get("status") == "created")
    errors  = sum(1 for r in results if r.get("status") == "error")

    if created:
        print(ok(f"  {created} PR(s) created successfully."))
    if errors:
        print(warn(f"  {errors} update(s) failed - see errors above."))
    if dry_run:
        print(c("  Dry run complete. No changes were made.", DIM))
