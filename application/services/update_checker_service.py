from typing import List, Dict, Optional
from domain.models.update_result import UpdateResult
from infrastructure.repository.smart_repo import SmartRepository


class UpdateCheckerService:
    _RISK = {"patch": "low", "minor": "medium", "major": "high"}

    def __init__(self, repo=None):
        self.repo = repo or SmartRepository()

    def check_updates(
        self,
        dependencies: Dict[str, str],
        locked: Dict[str, str],
        ignore: Optional[List[str]] = None,
        update_types: Optional[List[str]] = None,
    ) -> List[UpdateResult]:
        ignore = [p.lower() for p in (ignore or [])]
        update_types = update_types or ["patch", "minor", "major"]

        results: List[UpdateResult] = []
        for pkg, constraint_str in dependencies.items():
            if pkg.lower() in ignore:
                continue

            current = locked.get(pkg)
            if not current:
                continue

            try:
                versions = self.repo.get_versions(pkg)
            except Exception:
                continue

            if not versions:
                continue

            # get_versions returns strings; pick the true latest
            latest = self._pick_latest(versions)
            if not latest or latest == current:
                continue

            utype = self._classify(current, latest)
            if utype not in update_types:
                continue

            results.append(
                UpdateResult(
                    package=pkg,
                    current_version=current,
                    latest_version=latest,
                    update_type=utype,
                    risk_level=self._RISK[utype],
                    constraint=constraint_str,
                )
            )

        return results

    # ── helpers ──────────────────────────────────────────────────────────────

    def _pick_latest(self, versions) -> Optional[str]:
        """Return the highest version string from the list."""
        parsed = []
        for v in versions:
            s = str(v)
            try:
                parsed.append((tuple(int(x) for x in s.split(".")[:3]), s))
            except ValueError:
                continue
        if not parsed:
            return None
        return max(parsed, key=lambda t: t[0])[1]

    def _classify(self, current: str, latest: str) -> str:
        c = self._to_tuple(current)
        l = self._to_tuple(latest)
        if c[0] != l[0]:
            return "major"
        if len(c) > 1 and len(l) > 1 and c[1] != l[1]:
            return "minor"
        return "patch"

    def _to_tuple(self, version: str) -> tuple:
        try:
            return tuple(int(x) for x in version.split(".")[:3])
        except ValueError:
            return (0, 0, 0)
