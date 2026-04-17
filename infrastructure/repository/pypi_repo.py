import json
import os
import re
import time
import urllib.request
import urllib.error

from infrastructure.repository.abstract_repo import AbstractRepository


class PyPIRepository(AbstractRepository):
    """Fetches real package data from PyPI JSON API with file-based caching."""

    BASE_URL = "https://pypi.org/pypi"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.path.join(".mypm", "cache")
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    # ── internal helpers ──────────────────────────────────────

    def _cache_path(self, key: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", key)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _fetch(self, url: str, cache_key: str):
        path = self._cache_path(cache_key)
        if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < self.CACHE_TTL:
            with open(path) as f:
                return json.load(f)

        req = urllib.request.Request(url, headers={"User-Agent": "arbor/0.1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        except Exception:
            return None

        with open(path, "w") as f:
            json.dump(data, f)

        return data

    @staticmethod
    def _is_stable(ver: str) -> bool:
        return bool(re.match(r"^\d+(\.\d+)+$", ver))

    @staticmethod
    def _ver_key(ver: str):
        try:
            return tuple(int(x) for x in ver.split("."))
        except Exception:
            return (0,)

    # ── public API ────────────────────────────────────────────

    def get_versions(self, package_name: str, limit: int = 30) -> list:
        data = self._fetch(
            f"{self.BASE_URL}/{package_name}/json",
            f"meta_{package_name}",
        )
        if not data:
            return []
        stable = [
            v for v, files in data.get("releases", {}).items()
            if self._is_stable(v) and files
        ]
        sorted_vers = sorted(stable, key=self._ver_key)
        return sorted_vers[-limit:]

    def get_dependencies(self, package_name: str, version: str) -> list:
        data = self._fetch(
            f"{self.BASE_URL}/{package_name}/{version}/json",
            f"deps_{package_name}_{version.replace('.', '_')}",
        )
        if not data:
            return []

        requires = data.get("info", {}).get("requires_dist") or []
        deps = []
        for req in requires:
            # Split off environment marker
            parts = req.split(";", 1)
            marker = parts[1].strip() if len(parts) > 1 else ""

            # Skip optional extras and Python 2-only packages
            if "extra" in marker:
                continue
            if 'python_version < "3' in marker or "python_version < '3" in marker:
                continue
            if 'python_version == "2' in marker or "python_version == '2" in marker:
                continue

            req_clean = parts[0].strip()
            # Remove parentheses: "numpy (>=1.20)" → "numpy>=1.20"
            req_clean = re.sub(r"\s*\(([^)]+)\)", r"\1", req_clean).strip()
            # Match: <name> <constraint>
            m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([><=!,~][^\s].*)?$", req_clean)
            if not m:
                continue
            dep_name = m.group(1).strip()
            dep_con = re.sub(r"\s+", "", m.group(2) or ">=0")
            deps.append(f"{dep_name}{dep_con}")
        return deps

    def get_conflicts(self) -> list:
        return []

    def list_packages(self) -> list:
        return []

    def package_exists(self, name: str) -> bool:
        data = self._fetch(f"{self.BASE_URL}/{name}/json", f"meta_{name}")
        return data is not None
