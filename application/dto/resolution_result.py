from dataclasses import dataclass, field


@dataclass
class ResolutionResult:
    solution: dict = field(default_factory=dict)
    strategy: str = "sat"
    elapsed_ms: float = 0.0
    package_count: int = 0
    clause_count: int = 0

    def __post_init__(self):
        self.package_count = len(self.solution)

    def summary(self):
        return (
            f"Resolved {self.package_count} package(s) "
            f"using {self.strategy.upper()} strategy "
            f"in {self.elapsed_ms:.1f}ms"
        )
