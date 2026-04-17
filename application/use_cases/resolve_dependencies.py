from infrastructure.persistence.toml.reader import load_config
from application.services.resolution_service import ResolutionService
from application.services.lock_service import LockService


class ResolveDependencies:
    def __init__(self, strategy="sat"):
        self.strategy = strategy
        self.resolution_svc = ResolutionService()
        self.lock_svc = LockService()

    def execute(self) -> dict:
        data = load_config()
        deps = data.get("dependencies", {})
        if not deps:
            raise ValueError("No dependencies defined in mypm.toml")
        result = self.resolution_svc.resolve(deps, strategy=self.strategy)
        self.lock_svc.write(result.solution)
        return result
