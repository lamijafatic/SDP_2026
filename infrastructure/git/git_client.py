import subprocess
import os
from typing import Optional, List


class GitError(Exception):
    pass


class GitClient:
    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)

    def _run(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise GitError(
                f"git {' '.join(args)} failed:\n{result.stderr.strip()}"
            )
        return result

    def is_repo(self) -> bool:
        r = self._run("rev-parse", "--git-dir", check=False)
        return r.returncode == 0

    def get_current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def get_default_branch(self) -> str:
        r = self._run("symbolic-ref", "refs/remotes/origin/HEAD", check=False)
        if r.returncode == 0:
            return r.stdout.strip().split("/")[-1]
        for name in ("main", "master"):
            r = self._run("show-ref", "--verify", f"refs/heads/{name}", check=False)
            if r.returncode == 0:
                return name
        return "main"

    def branch_exists(self, name: str) -> bool:
        r = self._run("show-ref", "--verify", f"refs/heads/{name}", check=False)
        return r.returncode == 0

    def create_and_checkout_branch(self, name: str) -> None:
        if self.branch_exists(name):
            raise GitError(f"Branch '{name}' already exists locally.")
        self._run("checkout", "-b", name)

    def checkout(self, ref: str) -> None:
        self._run("checkout", ref)

    def delete_local_branch(self, name: str, force: bool = True) -> None:
        flag = "-D" if force else "-d"
        self._run("branch", flag, name, check=False)

    def stage_files(self, files: List[str]) -> None:
        existing = [f for f in files if os.path.exists(f)]
        if existing:
            self._run("add", *existing)

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def push_branch(self, branch: str, remote: str = "origin") -> None:
        self._run("push", "--set-upstream", remote, branch)

    def has_uncommitted_changes(self) -> bool:
        r = self._run("status", "--porcelain")
        return bool(r.stdout.strip())

    def stash(self) -> None:
        self._run("stash", "push", "--include-untracked", "-m", "arbor-bot-stash")

    def stash_pop(self) -> None:
        self._run("stash", "pop", check=False)

    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        r = self._run("remote", "get-url", remote, check=False)
        return r.stdout.strip() if r.returncode == 0 else None

    def get_config(self, key: str) -> Optional[str]:
        r = self._run("config", "--get", key, check=False)
        return r.stdout.strip() if r.returncode == 0 else None
