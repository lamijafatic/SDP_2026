from core.ui import section, ok, err, warn, info, bold, c, DIM, confirm
from application.services.environment_service import EnvironmentService
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    section("Clean Virtual Environment")

    env_svc = EnvironmentService()
    if not env_svc.exists():
        print(info("No virtual environment found — nothing to clean."))
        return 0

    print(warn("This will delete the .mypm/venv directory."))
    print(c("  You can recreate it with 'arbor install'.", DIM))

    if not confirm("Remove virtual environment?", default=False):
        print(info("Cancelled."))
        return 0

    removed = env_svc.remove()
    if removed:
        print(ok(f"Virtual environment {bold('.mypm/venv')} removed"))
        print(c("  Run 'arbor install' to recreate it.", DIM))
    else:
        print(err("Failed to remove virtual environment."))
        return 1
    return 0
