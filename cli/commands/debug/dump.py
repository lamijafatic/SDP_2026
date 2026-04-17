import json
import os
from core.ui import section, warn, ok, c, DIM
from application.services.project_service import ProjectService
from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.lock.lock_reader import read_lock


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    section("Project State Dump")

    config = load_config()
    locked = read_lock() if os.path.exists("mypm.lock") else {}

    state = {
        "project": config.get("project", {}),
        "dependencies": config.get("dependencies", {}),
        "lock": locked,
        "environment": {
            "path": ".mypm/venv",
            "exists": os.path.exists(".mypm/venv"),
        },
    }

    print(c("  mypm.toml + mypm.lock + environment state:", DIM))
    print()
    print(json.dumps(state, indent=2))
    print()
    return 0
