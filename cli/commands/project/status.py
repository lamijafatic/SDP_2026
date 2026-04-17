import os
from core.ui import section, ok, err, warn, info, table, bold, c, DIM, BRIGHT_GREEN, BRIGHT_RED, BRIGHT_YELLOW
from application.services.project_service import ProjectService
from application.services.lock_service import LockService
from application.services.environment_service import EnvironmentService
from application.services.dependecy_service import DependencyService


def run(args):
    svc = ProjectService()

    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    d = svc.get_project_info()
    lock_svc = LockService()
    env_svc = EnvironmentService()
    dep_svc = DependencyService()

    section("Project Status")

    # Project info
    print(c(f"  Project  : ", DIM) + bold(d["name"]) + c(f"  v{d['version']}", DIM))
    print(c(f"  Python   : {d['python']}", DIM))
    print()

    # Dependencies
    deps = dep_svc.list_direct()
    locked = lock_svc.read() if lock_svc.exists() else {}

    if deps:
        rows = []
        for name, constraint in deps.items():
            resolved = locked.get(name)
            status = c("✔ resolved", BRIGHT_GREEN) if resolved else c("? pending", BRIGHT_YELLOW)
            rows.append([name, constraint, resolved or c("—", DIM), status])
        print(c("  Dependencies:", DIM))
        table(["Package", "Constraint", "Locked Version", "Status"], rows)
    else:
        print(warn("No dependencies defined."))
        print()

    # Lock file
    if lock_svc.exists():
        print(ok(f"Lock file (mypm.lock) — {len(locked)} packages pinned"))
    else:
        print(err("Lock file missing — run 'arbor resolve'"))

    # Environment
    if env_svc.exists():
        print(ok(f"Virtual environment (.mypm/venv) — ready"))
        installed = env_svc.list_installed()
        if locked:
            missing = [p for p in locked if not any(i[0].lower() == p.lower() for i in installed)]
            if missing:
                print(warn(f"  {len(missing)} package(s) not yet installed: {', '.join(missing[:3])}..."))
            else:
                print(ok(f"  All {len(locked)} packages are installed"))
    else:
        print(err("Virtual environment missing — run 'arbor install'"))

    print()
    return 0
