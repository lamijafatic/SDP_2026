from core.ui import section, ok, warn, info, table, c, DIM, Spinner, bold
from application.services.project_service import ProjectService
from application.services.pr_bot_service import PRBotService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    section("Checking for Dependency Updates")

    sp = Spinner("Fetching latest versions from PyPI...")
    sp.start()
    try:
        bot_svc = PRBotService()
        updates = bot_svc.check_updates()
        sp.stop(success=True, msg=f"Found {len(updates)} update(s)")
    except Exception as e:
        sp.stop(success=False, msg=str(e))
        return 1

    if not updates:
        print(ok("All dependencies are up to date."))
        return 0

    rows = [
        [u.package, u.current_version, u.latest_version, u.update_type, u.risk_level]
        for u in updates
    ]
    print()
    table(["Package", "Current", "Latest", "Type", "Risk"], rows)
    print()

    major = [u for u in updates if u.update_type == "major"]
    minor = [u for u in updates if u.update_type == "minor"]
    patch = [u for u in updates if u.update_type == "patch"]

    if major:
        print(warn(f"  {len(major)} major update(s) – review carefully before merging"))
    if minor:
        print(info(f"  {len(minor)} minor update(s)"))
    if patch:
        print(ok(f"  {len(patch)} patch update(s)"))

    print()
    print(c("  Run 'arbor bot-run' to create GitHub PRs for these updates.", DIM))
    return 0
