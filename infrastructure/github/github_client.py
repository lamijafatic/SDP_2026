import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List


class GitHubAPIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"GitHub API {status}: {message}")


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "arbor-pm/0.1.0",
        }

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Any:
        url = f"{self.BASE_URL}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(
            url, data=body, headers=self._headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode()
                return json.loads(content) if content.strip() else {}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            try:
                msg = json.loads(body_text).get("message", body_text)
            except Exception:
                msg = body_text
            raise GitHubAPIError(e.code, msg)

    # ── Repo ────────────────────────────────────────────────────────────────

    def get_repo(self, owner: str, repo: str) -> Dict:
        return self._request("GET", f"/repos/{owner}/{repo}")

    def get_authenticated_user(self) -> Dict:
        return self._request("GET", "/user")

    # ── Pull Requests ────────────────────────────────────────────────────────

    def list_open_prs(self, owner: str, repo: str, head: str, base: str) -> List[Dict]:
        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={"head": head, "base": base, "state": "open"},
        )

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> Dict:
        return self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            {"title": title, "body": body, "head": head, "base": base, "draft": False},
        )

    def enable_auto_merge(
        self, owner: str, repo: str, pull_number: int, method: str = "squash"
    ) -> Dict:
        return self._request(
            "PUT",
            f"/repos/{owner}/{repo}/pulls/{pull_number}/merge",
            {"merge_method": method},
        )

    # ── Labels ───────────────────────────────────────────────────────────────

    def create_label(
        self, owner: str, repo: str, name: str, color: str, description: str = ""
    ) -> None:
        try:
            self._request(
                "POST",
                f"/repos/{owner}/{repo}/labels",
                {"name": name, "color": color, "description": description},
            )
        except GitHubAPIError as e:
            if e.status != 422:  # 422 = already exists
                raise

    def add_labels(
        self, owner: str, repo: str, issue_number: int, labels: List[str]
    ) -> None:
        self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
            {"labels": labels},
        )
