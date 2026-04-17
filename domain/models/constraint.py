import re
from domain.models.version import Version


class Constraint:
    def __init__(self, raw: str):
        self.raw = raw.strip()
        self.conditions = self._parse(self.raw)

    def _parse(self, raw):
        if not raw or raw in ("*", "any", ">=0"):
            return []

        conditions = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue

            match = re.match(r"(!=|>=|<=|~=|>|<|==)?\s*([\d][^\s,]*)", part)
            if not match:
                continue

            op, ver_str = match.groups()
            op = op or "=="

            # ~= X.Y  means  >= X.Y, == X.*  — treat as >= X.Y
            if op == "~=":
                op = ">="

            # Strip any non-numeric suffix (e.g. ".post1", ".dev0")
            ver_clean = re.match(r"^(\d+(?:\.\d+)*)", ver_str)
            if not ver_clean:
                continue
            ver_str = ver_clean.group(1)

            try:
                conditions.append((op, Version(ver_str)))
            except Exception:
                continue

        return conditions

    def is_satisfied_by(self, version) -> bool:
        if isinstance(version, str):
            version = Version(version)
        for op, v in self.conditions:
            t1, t2 = _pad(version.to_tuple(), v.to_tuple())
            if op == "==" and t1 != t2:
                return False
            elif op == "!=" and t1 == t2:
                return False
            elif op == ">=" and t1 < t2:
                return False
            elif op == "<=" and t1 > t2:
                return False
            elif op == ">" and t1 <= t2:
                return False
            elif op == "<" and t1 >= t2:
                return False
        return True

    def __str__(self):
        return self.raw


def _pad(t1, t2):
    n = max(len(t1), len(t2))
    return t1 + (0,) * (n - len(t1)), t2 + (0,) * (n - len(t2))
