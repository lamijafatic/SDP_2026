import json
import urllib.request
from typing import Optional


class ChangelogFetcher:
    _PRIORITY_KEYS = (
        "Changelog",
        "Changes",
        "Change Log",
        "History",
        "Release Notes",
        "What's New",
        "CHANGELOG",
    )

    def get_changelog_url(self, package: str, version: str) -> Optional[str]:
        try:
            url = f"https://pypi.org/pypi/{package}/{version}/json"
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            return None

        info = data.get("info", {})
        project_urls: dict = info.get("project_urls") or {}

        for key in self._PRIORITY_KEYS:
            if key in project_urls:
                return project_urls[key]

        # Fallback: homepage or source URL
        return info.get("home_page") or info.get("project_url") or None
