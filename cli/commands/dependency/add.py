from core.ui import section, ok, err, warn, info, table, bold, c, DIM, BRIGHT_CYAN
from application.use_cases.add_dependency import AddDependency
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    name = args.package
    constraint = args.constraint

    section(f"Adding Dependency: {name}")

    try:
        use_case = AddDependency()
        available = use_case.execute(name, constraint)
    except ValueError as e:
        print(err(str(e)))
        return 1

    print(ok(f"Added {bold(name)} {c(constraint, BRIGHT_CYAN)} to mypm.toml"))

    latest = available[-1] if available else "unknown"
    print(info(f"Latest available version: {bold(latest)}"))
    print(info(f"Available versions: {len(available)} total"))
    print()
    print(c("  Run 'arbor resolve' to update the lock file.", DIM))
    return 0
