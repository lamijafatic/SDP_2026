from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UpdateResult:
    package: str
    current_version: str
    latest_version: str
    update_type: str       # "patch" | "minor" | "major"
    risk_level: str        # "low" | "medium" | "high"
    constraint: str
    changelog_url: Optional[str] = field(default=None)

    def branch_name(self) -> str:
        safe = self.package.replace("-", "_").replace(".", "_").lower()
        safe_ver = self.latest_version.replace(".", "_")
        return f"arbor/update-{safe}-{safe_ver}"

    def commit_message(self) -> str:
        return (
            f"chore: update {self.package} from "
            f"{self.current_version} to {self.latest_version}"
        )

    def pr_title(self) -> str:
        return (
            f"chore(deps): update {self.package} "
            f"{self.current_version} → {self.latest_version}"
        )
