from core.ui import section, ok, err, warn, info, table, bold, c, Spinner, DIM, BRIGHT_CYAN, BRIGHT_GREEN
from application.use_cases.resolve_dependencies import ResolveDependencies
from application.services.project_service import ProjectService
from domain.exceptions.resolution_error import ResolutionError


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    project = svc.get_project_info()
    if project["dep_count"] == 0:
        print(warn("No dependencies defined. Use 'arbor add' to add packages."))
        return 1

    strategy = getattr(args, "strategy", "sat")
    section(f"Resolving Dependencies  [{strategy.upper()} Solver]")

    print(info(f"Project: {bold(project['name'])}"))
    print(info(f"Direct dependencies: {project['dep_count']}"))
    print()

    spinner = Spinner("Building constraint graph...")
    spinner.start()

    try:
        use_case = ResolveDependencies(strategy=strategy)
        result = use_case.execute()
        spinner.stop(success=True, msg="Constraint graph built")
    except ResolutionError as e:
        spinner.stop(success=False, msg="Resolution failed")
        print()
        print(err(str(e)))
        return 1
    except Exception as e:
        spinner.stop(success=False, msg="Unexpected error")
        print(err(str(e)))
        return 1

    print(ok(f"Solution found in {result.elapsed_ms:.1f}ms using {strategy.upper()}"))
    print()

    section("Resolved Versions")
    rows = [[pkg, c(ver, BRIGHT_GREEN)] for pkg, ver in sorted(result.solution.items())]
    table(["Package", "Version"], rows)

    print(ok(f"Lock file written: {bold('mypm.lock')}"))
    print(c(f"  {result.summary()}", DIM))
    print()
    print(c("  Run 'arbor install' to install these packages.", DIM))
    return 0
