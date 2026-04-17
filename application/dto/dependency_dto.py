from dataclasses import dataclass


@dataclass
class DependencyDTO:
    name: str
    constraint: str
    resolved_version: str = ""
    is_direct: bool = True
    source: str = ""

    def __str__(self):
        if self.resolved_version:
            return f"{self.name} {self.constraint} → {self.resolved_version}"
        return f"{self.name} {self.constraint}"
