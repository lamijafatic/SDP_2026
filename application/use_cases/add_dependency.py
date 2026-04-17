from application.services.dependecy_service import DependencyService


class AddDependency:
    def __init__(self):
        self.svc = DependencyService()

    def execute(self, name: str, constraint: str):
        available = self.svc.get_available_versions(name)
        if not available:
            raise ValueError(f"Unknown package: '{name}'. Use 'arbor search' to find packages.")
        self.svc.add(name, constraint)
        return available
