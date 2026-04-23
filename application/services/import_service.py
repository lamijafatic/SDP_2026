import os
import re
import ast
from typing import Dict, List, Tuple, Optional


class ImportService:
    """
    Detects and parses existing dependency files in a project directory,
    returning a unified {package: constraint} dict.
    """

    SUPPORTED = [
        ("requirements.txt",  "_parse_requirements"),
        ("requirements.in",   "_parse_requirements"),
        ("pyproject.toml",    "_parse_pyproject"),
        ("setup.cfg",         "_parse_setup_cfg"),
        ("setup.py",          "_parse_setup_py"),
        ("Pipfile",           "_parse_pipfile"),
    ]

    def detect(self, directory: str = ".") -> List[Tuple[str, str]]:
        """Return list of (filename, parser_method) for files found in directory."""
        found = []
        for filename, method in self.SUPPORTED:
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                found.append((filename, path, method))
        return found

    def parse_file(self, path: str) -> Dict[str, str]:
        """Auto-detect file type and parse it."""
        name = os.path.basename(path)
        for filename, method in self.SUPPORTED:
            if name == filename or name.startswith("requirements"):
                return getattr(self, method)(path)
        return {}

    def merge(self, sources: List[Dict[str, str]]) -> Dict[str, str]:
        """Merge multiple parsed dicts, later sources win on conflict."""
        merged: Dict[str, str] = {}
        for source in sources:
            merged.update(source)
        return merged

    # ── Parsers ──────────────────────────────────────────────────────────────

    def _parse_requirements(self, path: str) -> Dict[str, str]:
        deps: Dict[str, str] = {}
        with open(path, encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                # strip inline comments
                line = line.split("#")[0].strip()
                # strip environment markers (e.g. requests>=2.0; python_version>="3")
                line = line.split(";")[0].strip()
                name, constraint = self._split_dep(line)
                if name:
                    deps[self._normalize(name)] = constraint
        return deps

    def _parse_pyproject(self, path: str) -> Dict[str, str]:
        try:
            import toml
            data = toml.load(path)
        except Exception:
            return {}

        deps: Dict[str, str] = {}

        # PEP 621 standard: [project] dependencies = ["requests>=2.0"]
        project_deps = data.get("project", {}).get("dependencies", [])
        for dep in project_deps:
            name, constraint = self._split_dep(str(dep).split(";")[0].strip())
            if name:
                deps[self._normalize(name)] = constraint

        # Poetry: [tool.poetry.dependencies] = {requests = "^2.0"}
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for pkg, spec in poetry_deps.items():
            if pkg.lower() == "python":
                continue
            if isinstance(spec, str):
                constraint = self._poetry_to_pep(spec)
            elif isinstance(spec, dict):
                constraint = self._poetry_to_pep(spec.get("version", ">=0.1"))
            else:
                constraint = ">=0.1"
            deps[self._normalize(pkg)] = constraint

        return deps

    def _parse_setup_cfg(self, path: str) -> Dict[str, str]:
        deps: Dict[str, str] = {}
        try:
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(path)
            raw = cfg.get("options", "install_requires", fallback="")
            for line in raw.splitlines():
                line = line.strip().split(";")[0].strip()
                if not line:
                    continue
                name, constraint = self._split_dep(line)
                if name:
                    deps[self._normalize(name)] = constraint
        except Exception:
            pass
        return deps

    def _parse_setup_py(self, path: str) -> Dict[str, str]:
        deps: Dict[str, str] = {}
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                source = f.read()
            # Find install_requires=[...] via AST
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.keyword) and node.arg == "install_requires":
                    if isinstance(node.value, ast.List):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                line = str(elt.value).split(";")[0].strip()
                                name, constraint = self._split_dep(line)
                                if name:
                                    deps[self._normalize(name)] = constraint
        except Exception:
            pass
        return deps

    def _parse_pipfile(self, path: str) -> Dict[str, str]:
        deps: Dict[str, str] = {}
        try:
            import toml
            data = toml.load(path)
            packages = data.get("packages", {})
            for pkg, spec in packages.items():
                if isinstance(spec, str):
                    constraint = self._poetry_to_pep(spec) if spec != "*" else ">=0.1"
                elif isinstance(spec, dict):
                    v = spec.get("version", "*")
                    constraint = self._poetry_to_pep(v) if v != "*" else ">=0.1"
                else:
                    constraint = ">=0.1"
                deps[self._normalize(pkg)] = constraint
        except Exception:
            pass
        return deps

    # ── Helpers ──────────────────────────────────────────────────────────────

    _DEP_RE = re.compile(
        r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)"   # package name
        r"(\[.*?\])?"                                        # optional extras
        r"\s*([><=!~,\s][^\s;]*)?"                          # optional specifier
    )

    def _split_dep(self, dep: str) -> Tuple[str, str]:
        m = self._DEP_RE.match(dep.strip())
        if not m:
            return "", ">=0.1"
        name = m.group(1)
        spec = (m.group(4) or "").strip().rstrip(",").strip()
        if not spec:
            spec = ">=0.1"
        return name, spec

    def _normalize(self, name: str) -> str:
        return name.lower().replace("_", "-")

    def _poetry_to_pep(self, spec: str) -> str:
        """Convert Poetry/Pipfile version specs to PEP 440."""
        spec = spec.strip()
        if spec.startswith("^"):
            # ^1.2.3 -> >=1.2.3,<2.0.0
            ver = spec[1:]
            parts = ver.split(".")
            major = parts[0]
            return f">={ver},<{int(major) + 1}.0.0"
        if spec.startswith("~"):
            # ~1.2.3 -> >=1.2.3,<1.3.0
            ver = spec[1:]
            parts = ver.split(".")
            if len(parts) >= 2:
                return f">={ver},<{parts[0]}.{int(parts[1]) + 1}.0"
            return f">={ver}"
        if spec == "*":
            return ">=0.1"
        return spec
