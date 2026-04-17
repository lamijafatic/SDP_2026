from core.ui import section, ok, err, warn, c, bold, DIM
from application.services.dependecy_service import DependencyService
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    name = args.package
    section(f"Removing Dependency: {name}")

    try:
        dep_svc = DependencyService()
        dep_svc.remove(name)
    except KeyError as e:
        print(err(str(e)))
        return 1

    print(ok(f"Removed {bold(name)} from mypm.toml"))
    print(c("  Run 'arbor resolve' to update the lock file.", DIM))
    return 0
