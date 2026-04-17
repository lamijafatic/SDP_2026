import sys
from core.ui import section, ok, err, warn, info, bold, c, DIM, BRIGHT_GREEN, progress_bar, Spinner
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

    packages = lock_svc.read()
    dry_run = getattr(args, "dry_run", False)

    section("Installing Packages" + (" [DRY RUN]" if dry_run else ""))
    print(info(f"Packages to install: {len(packages)}"))
    print()

    if dry_run:
        rows = [[pkg, ver, c("would install", "\033[93m")] for pkg, ver in packages.items()]
        from core.ui import table
        table(["Package", "Version", "Action"], rows)
        print(info("Dry run — nothing was installed."))
        return 0

    env_svc = EnvironmentService()

    if not env_svc.exists():
        sp = Spinner("Creating virtual environment...")
        sp.start()
        try:
            env_svc.create()
            sp.stop(success=True, msg="Virtual environment created (.mypm/venv)")
        except Exception as e:
            sp.stop(success=False, msg="Failed to create virtual environment")
            print(err(str(e)))
            return 1
    else:
        print(ok("Virtual environment already exists"))

    print()
    total = len(packages)
    failed = []

    for i, (pkg, ver) in enumerate(packages.items()):
        progress_bar(i, total, label=f"Installing {pkg}=={ver}")
        success, error = env_svc.install_package(pkg, ver)
        if not success:
            failed.append((pkg, ver, error))

    progress_bar(total, total, label="Done")
    print()

    if failed:
        print()
        for pkg, ver, error in failed:
            print(err(f"Failed to install {pkg}=={ver}"))
            if error:
                print(c(f"    {error.strip()[:120]}", DIM))
        print(warn(f"{len(failed)} package(s) failed to install."))
    else:
        print(ok(f"All {total} packages installed successfully"))

    print(ok(f"Environment ready: {bold('.mypm/venv')}"))
    return 0 if not failed else 1
