import os
import sys
from core.ui import banner, section, ok, warn, info, prompt_input, bold, c, DIM
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()

    if svc.is_initialized():
        print(warn("Project already initialized (mypm.toml exists)."))
        data = svc.get_project_info()
        print(info(f"Project: {bold(data['name'])}  |  {data['dep_count']} dependencies"))
        return 0

    banner()
    section("Initialize New Project")

    name = getattr(args, "name", None)
    if not name:
        name = prompt_input("Project name", default="my_project")

    python_ver = getattr(args, "python", None)
    if not python_ver:
        default_py = f"{sys.version_info.major}.{sys.version_info.minor}"
        python_ver = prompt_input("Python version", default=default_py)

    description = prompt_input("Description (optional)", default="")
    print()

    svc.create_project(name, python_version=python_ver, description=description)



    print(ok(f"Project {bold(name)} initialized"))
    print(ok(f"Configuration file created: {bold('mypm.toml')}"))
    print(ok("Project structure created"))
    print(ok(f"Virtual environment: {bold('.venv/')}"))
    print(ok(f"Source: {bold('src/')}  |  Tests: {bold('tests/')}"))
    print()

    print(c("  Next steps:", DIM))
    print(c(f"    source .venv/bin/activate   — activate virtual environment", DIM))
    print(c(f"    arbor add numpy '>=1.20'   — add a dependency", DIM))
    print(c(f"    arbor resolve              — resolve all constraints", DIM))
    print(c(f"    arbor install              — install dependencies", DIM))
    print()
    return 0
