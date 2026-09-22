import os
import subprocess
from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.toml.writer import save_config


class ProjectService:
    CONFIG_FILE = "mypm.toml"
    LOCK_FILE = "mypm.lock"
    ENV_PATH = ".mypm/venv"

    def is_initialized(self):
        return os.path.exists(self.CONFIG_FILE)

    def create_project(self, name, python_version="3.11", description=""):
        # ---------- CONFIG ----------
        data = {
            "project": {
                "name": name,
                "version": "0.1.0",
                "python": python_version,
                "description": description,
            },
            "dependencies": {},
        }

        # ---------- CREATE ROOT ----------
        os.makedirs(name, exist_ok=True)
        os.chdir(name)

        # ---------- STRUCTURE ----------
        os.makedirs(f"src/{name}", exist_ok=True)
        os.makedirs("tests", exist_ok=True)
        os.makedirs("assets", exist_ok=True)
        os.makedirs(".mypm", exist_ok=True)

        # ---------- FILES ----------

        with open(f"src/{name}/main.py", "w") as f:
            f.write(
f"""def main():
    print("Hello from {name}")

if __name__ == "__main__":
    main()
"""
            )

        open(f"src/{name}/__init__.py", "w").close()

        with open("tests/test_basic.py", "w") as f:
            f.write(
"""def test_example():
    assert True
"""
            )

        with open("README.md", "w") as f:
            f.write(f"# {name}\n\n{description}\n")

        with open(".gitignore", "w") as f:
            f.write(
"""__pycache__/
*.pyc
.venv/
.mypm/
"""
            )

        with open("requirements.txt", "w") as f:
            f.write("")

        with open("pyproject.toml", "w") as f:
            f.write(
f"""
[project]
name = "{name}"
version = "0.1.0"
requires-python = ">= {python_version}"
"""
            )

        # ---------- VIRTUAL ENV ----------
        try:
            subprocess.run(["python", "-m", "venv", ".venv"], check=True)
        except Exception:
            print("Warning: Could not create virtual environment")

        # ---------- SAVE CONFIG ----------
        save_config(data)

        return data

    def get_project_info(self):
        data = load_config()
        project = data.get("project", {})
        deps = data.get("dependencies", {})
        lock_exists = os.path.exists(self.LOCK_FILE)
        env_exists = os.path.exists(self.ENV_PATH)

        return {
            "name": project.get("name", "unnamed"),
            "version": project.get("version", "0.1.0"),
            "python": project.get("python", "3.x"),
            "description": project.get("description", ""),
            "dep_count": len(deps),
            "lock_exists": lock_exists,
            "env_exists": env_exists,
            "deps": deps,
        }

    def health_check(self):
        issues = []
        ok_items = []

        if not os.path.exists(self.CONFIG_FILE):
            issues.append("No mypm.toml found — run 'vertex init' first")
        else:
            ok_items.append("Configuration file (mypm.toml) exists")

        if os.path.exists(self.LOCK_FILE):
            ok_items.append("Lock file (mypm.lock) is present")
        else:
            issues.append("No lock file — run 'vertex resolve' to generate one")

        if os.path.exists(self.ENV_PATH):
            ok_items.append("Virtual environment (.mypm/venv) exists")
        else:
            issues.append("No virtual environment — run 'vertex install' to create one")

        if self.is_initialized():
            data = load_config()
            deps = data.get("dependencies", {})
            if deps:
                ok_items.append(f"{len(deps)} dependenc{'y' if len(deps)==1 else 'ies'} defined")
            else:
                issues.append("No dependencies defined — use 'vertex add'")

        return ok_items, issues