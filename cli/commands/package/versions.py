from core.ui import section, warn, info, bold, c, DIM, BRIGHT_GREEN, BRIGHT_YELLOW, BRIGHT_CYAN, Spinner
from application.services.dependecy_service import DependencyService
from infrastructure.repository.smart_repo import SmartRepository
from infrastructure.persistence.toml.reader import load_config
import os


def run(args):
    pkg = args.package
    section(f"Available Versions: {pkg}")

    repo = SmartRepository()
    source_label = c("PyPI (live)", BRIGHT_CYAN) if repo._use_pypi(pkg) else c("local registry", "\033[36m")

    sp = Spinner(f"Fetching versions from {source_label}...")
    sp.start()
    svc = DependencyService()
    versions = svc.get_available_versions(pkg)
    sp.stop(success=True, msg=f"Fetched {len(versions)} versions")

    if not versions:
        print(warn(f"Package '{pkg}' not found."))
        print(info("Use 'arbor search' to find available packages."))
        return 1

    current_constraint = None
    if os.path.exists("mypm.toml"):
        try:
            data = load_config()
            current_constraint = data.get("dependencies", {}).get(pkg)
        except Exception:
            pass

    print(info(f"Package: {bold(pkg)}"))
    print(info(f"Source: {source_label}"))
    print(info(f"Total versions: {len(versions)}"))
    if current_constraint:
        print(info(f"Current constraint: {c(current_constraint, BRIGHT_YELLOW)}"))
    print()

    latest = versions[-1]
    rows = []
    for ver in reversed(versions):
        tag = ""
        if ver == latest:
            tag = c("latest", BRIGHT_GREEN)
        elif current_constraint:
            from domain.models.constraint import Constraint
            from domain.models.version import Version
            try:
                if Constraint(current_constraint).is_satisfied_by(Version(ver)):
                    tag = c("compatible", "\033[36m")
            except Exception:
                pass
        rows.append([c(ver, BRIGHT_GREEN if ver == latest else ""), tag])

    from core.ui import table
    table(["Version", "Status"], rows)

    print()
    print(c(f"  Add with: arbor add {pkg} '>=X.Y'", DIM))
    return 0
