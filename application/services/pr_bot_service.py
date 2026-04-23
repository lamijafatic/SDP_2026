import os
import re
from typing import List, Dict, Tuple, Optional

from domain.models.update_result import UpdateResult
from application.services.update_checker_service import UpdateCheckerService
from infrastructure.git.git_client import GitClient, GitError
from infrastructure.github.github_client import GitHubClient, GitHubAPIError
from infrastructure.github.changelog_fetcher import ChangelogFetcher
from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.toml.writer import save_config
from infrastructure.persistence.lock.lock_reader import read_lock
from infrastructure.persistence.lock.lock_writer import write_lock


class PRBotError(Exception):
    pass


_LABEL_DEFS = {
    "dependencies": ("0075ca", "Dependency updates"),
    "major-update":  ("d93f0b", "Major version update – high risk"),
    "minor-update":  ("fbca04", "Minor version update – medium risk"),
    "patch-update":  ("0e8a16", "Patch version update – low risk"),
}


class PRBotService:
    LOCK_FILE = "mypm.lock"
    CONFIG_FILE = "mypm.toml"

    def __init__(self):
        self.checker = UpdateCheckerService()
        self.git = GitClient()
        self.changelog = ChangelogFetcher()

    # ── Public API ──────────────────────────────────────────────────────────

    def check_updates(self) -> List[UpdateResult]:
        config = load_config()
        locked = self._read_lock_safe()
        bot = config.get("bot", {})
        return self.checker.check_updates(
            dependencies=config.get("dependencies", {}),
            locked=locked,
            ignore=bot.get("ignore", []),
            update_types=bot.get("update_types", ["patch", "minor", "major"]),
        )

    def run(self, dry_run: bool = False, on_progress=None) -> List[Dict]:
        config = load_config()
        bot = config.get("bot", {})

        token = bot.get("github_token") or os.environ.get("GITHUB_TOKEN", "")
        if not token and not dry_run:
            raise PRBotError(
                "GitHub token not found.\n"
                "Set GITHUB_TOKEN env var or add 'github_token' under [bot] in mypm.toml."
            )

        updates = self.check_updates()
        if not updates:
            return []

        if dry_run:
            return [
                {"update": u, "pr_url": None, "status": "dry_run"} for u in updates
            ]

        github = GitHubClient(token)
        owner, repo_name = self._parse_repo(bot, github)
        base = bot.get("base_branch") or self.git.get_default_branch()
        group = bot.get("group_updates", False)

        original_branch = self.git.get_current_branch()
        stashed = False
        results: List[Dict] = []

        try:
            if self.git.has_uncommitted_changes():
                self.git.stash()
                stashed = True

            if group:
                result = self._process_group(
                    updates, config, github, owner, repo_name, base, bot, on_progress
                )
                results.append(result)
            else:
                for update in updates:
                    result = self._process_single(
                        update, config, github, owner, repo_name, base, bot, on_progress
                    )
                    results.append(result)
        finally:
            try:
                self.git.checkout(original_branch)
            except Exception:
                pass
            if stashed:
                self.git.stash_pop()

        return results

    # ── Single-package PR ───────────────────────────────────────────────────

    def _process_single(
        self,
        update: UpdateResult,
        config: Dict,
        github: GitHubClient,
        owner: str,
        repo: str,
        base: str,
        bot: Dict,
        on_progress=None,
    ) -> Dict:
        branch = update.branch_name()
        if on_progress:
            on_progress(f"Processing {update.package} {update.current_version} → {update.latest_version}")

        # Fetch changelog before touching git (network call first)
        update.changelog_url = self.changelog.get_changelog_url(
            update.package, update.latest_version
        )

        # Check for existing open PR
        git_user = self._get_git_user(github)
        head_ref = f"{git_user}:{branch}"
        existing = github.list_open_prs(owner, repo, head_ref, base)
        if existing:
            return {
                "update": update,
                "pr_url": existing[0]["html_url"],
                "status": "exists",
            }

        try:
            self.git.create_and_checkout_branch(branch)
            self._apply_single_update(update)
            self.git.stage_files([self.CONFIG_FILE, self.LOCK_FILE])
            self.git.commit(update.commit_message())
            self.git.push_branch(branch)

            pr = self._open_pr(github, owner, repo, base, branch, [update], bot)
            return {
                "update": update,
                "pr_url": pr["html_url"],
                "pr_number": pr["number"],
                "status": "created",
            }
        except Exception as e:
            self._rollback(branch)
            return {"update": update, "pr_url": None, "status": "error", "error": str(e)}

    # ── Grouped PR ──────────────────────────────────────────────────────────

    def _process_group(
        self,
        updates: List[UpdateResult],
        config: Dict,
        github: GitHubClient,
        owner: str,
        repo: str,
        base: str,
        bot: Dict,
        on_progress=None,
    ) -> Dict:
        branch = "arbor/update-dependencies"
        if on_progress:
            on_progress(f"Processing {len(updates)} updates as a grouped PR")

        for u in updates:
            u.changelog_url = self.changelog.get_changelog_url(u.package, u.latest_version)

        try:
            self.git.create_and_checkout_branch(branch)
            for update in updates:
                self._apply_single_update(update)
            self.git.stage_files([self.CONFIG_FILE, self.LOCK_FILE])
            names = ", ".join(u.package for u in updates[:3])
            suffix = f" (+{len(updates) - 3} more)" if len(updates) > 3 else ""
            self.git.commit(f"chore: update {names}{suffix}")
            self.git.push_branch(branch)

            pr = self._open_pr(github, owner, repo, base, branch, updates, bot)
            return {
                "updates": updates,
                "pr_url": pr["html_url"],
                "pr_number": pr["number"],
                "status": "created",
            }
        except Exception as e:
            self._rollback(branch)
            return {"updates": updates, "pr_url": None, "status": "error", "error": str(e)}

    # ── File mutation ────────────────────────────────────────────────────────

    def _apply_single_update(self, update: UpdateResult) -> None:
        # Update constraint in mypm.toml
        config = load_config()
        config.setdefault("dependencies", {})[update.package] = f">={update.latest_version}"
        save_config(config)

        # Bump version in lock file
        lock = self._read_lock_safe()
        lock[update.package] = update.latest_version
        write_lock(lock)

    # ── GitHub helpers ───────────────────────────────────────────────────────

    def _open_pr(
        self,
        github: GitHubClient,
        owner: str,
        repo: str,
        base: str,
        branch: str,
        updates: List[UpdateResult],
        bot: Dict,
    ) -> Dict:
        title, body = self._build_pr_content(updates)
        pr = github.create_pull_request(owner, repo, title, body, branch, base)

        if bot.get("labels", True):
            labels = self._pick_labels(updates)
            self._ensure_labels(github, owner, repo, labels)
            github.add_labels(owner, repo, pr["number"], labels)

        if bot.get("auto_merge", False):
            try:
                github.enable_auto_merge(owner, repo, pr["number"])
            except (GitHubAPIError, Exception):
                pass  # auto-merge may require branch-protection rules; non-fatal

        return pr

    def _build_pr_content(self, updates: List[UpdateResult]) -> Tuple[str, str]:
        rows = "\n".join(
            f"| `{u.package}` | `{u.current_version}` | `{u.latest_version}` "
            f"| {u.update_type} | {u.risk_level} |"
            + (f"\n| | | [changelog]({u.changelog_url}) | | |" if u.changelog_url else "")
            for u in updates
        )
        table = (
            "| Package | From | To | Type | Risk |\n"
            "|---------|------|----|------|------|\n"
            f"{rows}"
        )

        if len(updates) == 1:
            u = updates[0]
            title = u.pr_title()
        else:
            title = f"chore(deps): update {len(updates)} dependencies"

        body = (
            f"## Dependency Update{'s' if len(updates) > 1 else ''}\n\n"
            f"{table}\n\n"
            "---\n"
            "*Generated by **arbor-pm** automated dependency bot*"
        )
        return title, body

    def _pick_labels(self, updates: List[UpdateResult]) -> List[str]:
        types = {u.update_type for u in updates}
        labels = ["dependencies"]
        if "major" in types:
            labels.append("major-update")
        elif "minor" in types:
            labels.append("minor-update")
        else:
            labels.append("patch-update")
        return labels

    def _ensure_labels(
        self, github: GitHubClient, owner: str, repo: str, labels: List[str]
    ) -> None:
        for label in labels:
            if label in _LABEL_DEFS:
                color, desc = _LABEL_DEFS[label]
                github.create_label(owner, repo, label, color, desc)

    # ── Repo / user detection ────────────────────────────────────────────────

    def _parse_repo(self, bot: Dict, github: GitHubClient) -> Tuple[str, str]:
        slug = bot.get("github_repo", "")
        if slug and "/" in slug:
            owner, repo = slug.split("/", 1)
            return owner, repo

        remote_url = self.git.get_remote_url()
        if not remote_url:
            raise PRBotError(
                "Cannot determine GitHub repo.\n"
                "Set 'github_repo = \"owner/repo\"' under [bot] in mypm.toml, "
                "or make sure the project has a git remote named 'origin'."
            )
        m = re.search(r"github\.com[:/](.+?)/(.+?)(?:\.git)?$", remote_url)
        if not m:
            raise PRBotError(
                f"Remote URL does not look like a GitHub repo: {remote_url}\n"
                "Set 'github_repo = \"owner/repo\"' under [bot] in mypm.toml."
            )
        return m.group(1), m.group(2)

    def _get_git_user(self, github: GitHubClient) -> str:
        try:
            return github.get_authenticated_user().get("login", "")
        except Exception:
            return ""

    # ── Rollback ─────────────────────────────────────────────────────────────

    def _rollback(self, branch: str) -> None:
        try:
            self.git.checkout(self.git.get_current_branch())
        except Exception:
            pass
        self.git.delete_local_branch(branch)

    # ── Lock helpers ─────────────────────────────────────────────────────────

    def _read_lock_safe(self) -> Dict:
        if os.path.exists(self.LOCK_FILE):
            try:
                return read_lock()
            except Exception:
                pass
        return {}
