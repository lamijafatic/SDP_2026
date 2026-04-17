import os
import subprocess
import sys
from core.ui import section, ok, err, warn, info, bold, c, DIM, Spinner
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    section("Build Distribution Package")

    if not os.path.exists("setup.py") and not os.path.exists("pyproject.toml"):
        print(warn("No setup.py or pyproject.toml found."))
        print(info("A setup.py already exists in this project — trying anyway."))

    d = svc.get_project_info()
    print(info(f"Building {bold(d['name'])} v{d['version']}"))
    print()

    sp = Spinner("Installing build tools...")
    sp.start()
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "build", "--quiet"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sp.stop(success=False, msg="Failed to install build tools")
        print(c(result.stderr[:200], DIM))
        return 1
    sp.stop(success=True, msg="Build tools ready")

    sp = Spinner("Building source distribution and wheel...")
    sp.start()
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", "dist/"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sp.stop(success=False, msg="Build failed")
        print(c(result.stdout[-500:], DIM))
        print(c(result.stderr[-500:], DIM))
        return 1
    sp.stop(success=True, msg="Build complete")

    print()
    if os.path.exists("dist/"):
        files = os.listdir("dist/")
        for f in files:
            size = os.path.getsize(os.path.join("dist/", f))
            print(ok(f"{f}  ({size // 1024} KB)"))
    print(ok(f"Artifacts saved to {bold('dist/')}"))
    return 0
