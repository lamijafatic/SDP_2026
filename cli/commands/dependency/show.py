import os
from core.ui import section, warn, info, table, bold, c, DIM
from application.services.dependecy_service import DependencyService
from application.services.project_service import ProjectService
from infrastructure.persistence.lock.lock_reader import read_lock


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    dep_svc = DependencyService()
    deps = dep_svc.list_direct()

    section("Dependencies")

    if not deps:
        print(warn("No dependencies defined."))
        print(info("Use 'arbor add <package> <constraint>' to add packages."))
        return 0

    locked = {}
    if os.path.exists("mypm.lock"):
        locked = read_lock()

    rows = []
    for name, constraint in deps.items():
        resolved = locked.get(name, c("(not resolved)", DIM))
        available = dep_svc.get_available_versions(name)
        latest = available[-1] if available else "?"
        rows.append([name, constraint, resolved, latest])

    table(["Package", "Constraint", "Resolved", "Latest"], rows)
    print(c(f"  {len(deps)} direct dependenc{'y' if len(deps)==1 else 'ies'}", DIM))

    if not locked:
        print(info("Run 'arbor resolve' to resolve versions."))
    return 0
