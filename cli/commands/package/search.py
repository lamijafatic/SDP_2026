from core.ui import section, warn, info, table, bold, c, DIM, BRIGHT_GREEN, BRIGHT_CYAN, Spinner
from application.services.dependecy_service import DependencyService
from infrastructure.repository.smart_repo import SmartRepository


def run(args):
    query = args.query
    section(f"Search: '{query}'")

    sp = Spinner(f"Searching for '{query}'...")
    sp.start()

    svc = DependencyService()
    matches = svc.search(query)
    sp.stop(success=True, msg=f"Search complete")

    if not matches:
        print(warn(f"No packages found matching '{query}'."))
        print(info("Try an exact PyPI package name, e.g. 'arbor add requests >=2.28'"))
        return 0

    repo = SmartRepository()
    rows = []
    for pkg in matches:
        versions = svc.get_available_versions(pkg)
        latest = versions[-1] if versions else "?"
        count = len(versions)
        source = c("local registry", "\033[36m") if not repo._use_pypi(pkg) else c("PyPI", BRIGHT_CYAN)
        rows.append([bold(pkg), c(latest, BRIGHT_GREEN), f"{count} versions", source])

    table(["Package", "Latest", "Available", "Source"], rows)
    print(c(f"  {len(matches)} package(s) found.", DIM))
    print(info("Use 'arbor versions <package>' to see all versions."))
    print(info("Use 'arbor add <package> <constraint>' to add a dependency."))
    return 0
