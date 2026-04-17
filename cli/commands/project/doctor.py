from core.ui import section, ok, err, warn, info, bold, c, DIM, BRIGHT_YELLOW
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    section("Project Health Check")

    ok_items, issues = svc.health_check()

    for item in ok_items:
        print(ok(item))

    for issue in issues:
        print(err(issue))

    print()
    if not issues:
        print(c("  All checks passed — project is healthy!", bold("") + ""))
        print(ok("Project is ready to use"))
    else:
        print(warn(f"{len(issues)} issue(s) found."))
        print(info("Run suggested commands above to resolve them."))

    return 0 if not issues else 1
