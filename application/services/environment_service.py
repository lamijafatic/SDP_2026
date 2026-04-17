import os
import subprocess
import sys

ENV_PATH = ".mypm/venv"


class EnvironmentService:
    def __init__(self, env_path=ENV_PATH):
        self.env_path = env_path

    def exists(self):
        return os.path.exists(self.env_path)

    def get_pip(self):
        if os.name == "nt":
            return os.path.join(self.env_path, "Scripts", "pip")
        return os.path.join(self.env_path, "bin", "pip")

    def get_python(self):
        if os.name == "nt":
            return os.path.join(self.env_path, "Scripts", "python")
        return os.path.join(self.env_path, "bin", "python")

    def create(self, on_progress=None):
        os.makedirs(os.path.dirname(self.env_path) or ".", exist_ok=True)
        if on_progress:
            on_progress("Creating virtual environment...")
        subprocess.run(
            [sys.executable, "-m", "venv", self.env_path],
            check=True,
            capture_output=True,
        )

    def install_package(self, pkg, version):
        pip = self.get_pip()
        result = subprocess.run(
            [pip, "install", f"{pkg}=={version}", "--quiet"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stderr

    def install_packages(self, packages: dict, on_progress=None):
        results = {}
        total = len(packages)
        for i, (pkg, version) in enumerate(packages.items()):
            if on_progress:
                on_progress(i, total, pkg, version)
            success, err = self.install_package(pkg, version)
            results[pkg] = {"version": version, "success": success, "error": err}
        if on_progress:
            on_progress(total, total, "", "")
        return results

    def remove(self):
        import shutil
        if os.path.exists(self.env_path):
            shutil.rmtree(self.env_path)
            return True
        return False

    def list_installed(self):
        if not self.exists():
            return []
        pip = self.get_pip()
        result = subprocess.run(
            [pip, "list", "--format=freeze"],
            capture_output=True, text=True,
        )
        packages = []
        for line in result.stdout.strip().splitlines():
            if "==" in line:
                name, ver = line.split("==", 1)
                packages.append((name.strip(), ver.strip()))
        return packages
