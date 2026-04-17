import os
from core.ui import section, ok, warn, info, table, bold, c, DIM, BRIGHT_GREEN, BRIGHT_RED
from application.services.project_service import ProjectService


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    d = svc.get_project_info()
    section("Project Information")

    rows = [
        ["Name", bold(d["name"])],
        ["Version", d["version"]],
        ["Python", d["python"]],
    ]
    if d.get("description"):
        rows.append(["Description", d["description"]])
    rows.append(["Direct dependencies", str(d["dep_count"])])
    rows.append(["Lock file", c("✔ present", BRIGHT_GREEN) if d["lock_exists"] else c("✘ missing", BRIGHT_RED)])
    rows.append(["Virtual env", c("✔ present", BRIGHT_GREEN) if d["env_exists"] else c("✘ missing", BRIGHT_RED)])
    rows.append(["Config file", "mypm.toml"])

    table(["Field", "Value"], rows)

    if d["deps"]:
        section("Direct Dependencies")
        dep_rows = [[name, constraint] for name, constraint in d["deps"].items()]
        table(["Package", "Constraint"], dep_rows)

    if not d["lock_exists"]:
        print(info("Run 'arbor resolve' to generate a lock file."))
    if not d["env_exists"]:
        print(info("Run 'arbor install' to set up the virtual environment."))
    return 0
