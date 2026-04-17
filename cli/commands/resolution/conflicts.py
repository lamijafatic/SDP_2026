from core.ui import section, warn, info, table, bold, c, BRIGHT_RED, BRIGHT_YELLOW, DIM
from application.services.resolution_service import ResolutionService


def run(args):
    section("Known Package Conflicts")

    svc = ResolutionService()
    conflicts = svc.detect_conflicts()

    if not conflicts:
        print(info("No conflicts found in the registry."))
        return 0

    rows = []
    for con in conflicts:
        rows.append([
            c(con["package1"], BRIGHT_RED),
            con["version1"],
            c(con["package2"], BRIGHT_RED),
            con["version2"],
        ])

    table(["Package A", "Version A", "Package B", "Version B"], rows)
    print(c(f"  {len(conflicts)} conflict(s) registered in the package registry.", DIM))
    print()
    print(c("  Conflicting packages cannot be installed together.", BRIGHT_YELLOW))
    print(c("  The SAT solver automatically excludes these combinations.", DIM))
    return 0
