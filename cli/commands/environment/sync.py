from core.ui import section, ok, err, warn, info, table, bold, c, DIM, Spinner, BRIGHT_GREEN, BRIGHT_RED
from application.services.project_service import ProjectService
from application.services.lock_service import LockService
from application.services.environment_service import EnvironmentService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    lock_svc = LockService()
    if not lock_svc.exists():
        print(err("No lock file found."))
        print(info("Run 'arbor resolve' first to generate mypm.lock"))
        return 1

    section("Syncing Environment with Lock File")

    packages = lock_svc.read()
    env_svc = EnvironmentService()

    if not env_svc.exists():
        sp = Spinner("Creating virtual environment...")
        sp.start()
        try:
            env_svc.create()
            sp.stop(success=True, msg="Virtual environment created")
        except Exception as e:
            sp.stop(success=False, msg="Failed")
            print(err(str(e)))
            return 1

    sp = Spinner("Checking installed packages...")
    sp.start()
    installed = {name.lower(): ver for name, ver in env_svc.list_installed()}
    sp.stop(success=True, msg="Current environment scanned")

    to_install = {}
    to_update = {}

    for pkg, ver in packages.items():
        key = pkg.lower()
        if key not in installed:
            to_install[pkg] = ver
        elif installed[key] != ver:
            to_update[pkg] = (installed[key], ver)

    if not to_install and not to_update:
        print(ok("Environment is already in sync with lock file"))
        return 0

    if to_install:
        print(info(f"Packages to install: {len(to_install)}"))
    if to_update:
        print(info(f"Packages to update: {len(to_update)}"))
    print()

    failed = []
    total = len(to_install) + len(to_update)
    done = 0

    for pkg, ver in {**to_install, **{p: v[1] for p, v in to_update.items()}}.items():
        from core.ui import progress_bar
        progress_bar(done, total, label=f"Syncing {pkg}=={ver}")
        success, error = env_svc.install_package(pkg, ver)
        if not success:
            failed.append((pkg, ver))
        done += 1

    from core.ui import progress_bar
    progress_bar(total, total, label="Done")
    print()

    if failed:
        for pkg, ver in failed:
            print(err(f"Failed: {pkg}=={ver}"))
    else:
        print(ok("Environment synced successfully"))

    return 0 if not failed else 1
