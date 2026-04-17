import os
import sys
import subprocess

ENV_PATH = ".mypm/venv"


class VenvManager:
    def __init__(self, path=ENV_PATH):
        self.path = path

    @property
    def pip(self):
        if os.name == "nt":
            return os.path.join(self.path, "Scripts", "pip")
        return os.path.join(self.path, "bin", "pip")

    @property
    def python(self):
        if os.name == "nt":
            return os.path.join(self.path, "Scripts", "python")
        return os.path.join(self.path, "bin", "python")

    def exists(self):
        return os.path.exists(self.path)

    def create(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        subprocess.run(
            [sys.executable, "-m", "venv", self.path],
            check=True,
            capture_output=True,
        )

    def install(self, package, version):
        result = subprocess.run(
            [self.pip, "install", f"{package}=={version}", "--quiet"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stderr

    def uninstall(self, package):
        result = subprocess.run(
            [self.pip, "uninstall", package, "-y", "--quiet"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def list_packages(self):
        if not self.exists():
            return []
        result = subprocess.run(
            [self.pip, "list", "--format=freeze"],
            capture_output=True, text=True,
        )
        pkgs = []
        for line in result.stdout.strip().splitlines():
            if "==" in line:
                name, ver = line.split("==", 1)
                pkgs.append((name.strip(), ver.strip()))
        return pkgs

    def destroy(self):
        import shutil
        if self.exists():
            shutil.rmtree(self.path)
