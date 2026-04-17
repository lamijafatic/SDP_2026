from core.ui import section, info, table, bold, c, DIM, BRIGHT_GREEN
from infrastructure.repository.smart_repo import SmartRepository


def run(args):
    section("Package Registry")

    repo = SmartRepository()
    packages = repo.list_packages()

    rows = []
    for pkg in sorted(packages):
        versions = repo.get_versions(pkg)
        if not versions:
            continue
        latest = sorted(versions, key=lambda v: tuple(int(x) for x in v.split(".")))[-1]
        deps_of_latest = repo.get_dependencies(pkg, latest)
        deps_str = (
            ", ".join(
                re.split(r"[><=!~]", d)[0].strip()
                for d in deps_of_latest
            )
            if deps_of_latest else c("none", DIM)
        )
        rows.append([bold(pkg), c(latest, BRIGHT_GREEN), str(len(versions)), deps_str])

    import re
    table(["Package", "Latest", "Versions", "Requires"], rows)
    print(c(f"  {len(packages)} packages in local registry", DIM))
    print()
    print(info("Use 'arbor search <query>' to search by name."))
    print(info("Use 'arbor versions <pkg>' to see all versions."))
    print(info("Any PyPI package works: arbor add requests '>=2.28'"))
    return 0
