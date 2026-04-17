from core.ui import section, ok, err, warn, info, table, bold, c, DIM, Spinner
from application.services.dependecy_service import DependencyService
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    dep_svc = DependencyService()
    target = getattr(args, "package", None)
    deps = dep_svc.list_direct()

    if not deps:
        print(warn("No dependencies to update."))
        return 0

    packages_to_update = {target: deps[target]} if target else deps

    if target and target not in deps:
        print(err(f"Package '{target}' is not in dependencies."))
        return 1

    section("Updating Dependencies")
    updated = []

    for name, old_constraint in packages_to_update.items():
        sp = Spinner(f"Checking latest for {name}...")
        sp.start()
        available = dep_svc.get_available_versions(name)
        sp.stop(success=True, msg=f"Checked {name}")

        if not available:
            print(warn(f"  No versions found for {name}"))
            continue

        latest = available[-1]
        new_constraint = f">={latest}"

        if old_constraint != new_constraint:
            dep_svc.update_constraint(name, new_constraint)
            updated.append([name, old_constraint, new_constraint, latest])
            print(ok(f"  {bold(name)}: {old_constraint} → {new_constraint}"))
        else:
            print(info(f"  {name}: already up to date ({old_constraint})"))

    print()
    if updated:
        print(ok(f"Updated {len(updated)} package(s)"))
        print(c("  Run 'arbor resolve' to regenerate the lock file.", DIM))
    else:
        print(info("All packages are already at their latest constraints."))
    return 0
