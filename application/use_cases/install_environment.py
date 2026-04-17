from application.services.environment_service import EnvironmentService
from application.services.lock_service import LockService


class InstallEnvironment:
    def execute(self, on_progress=None):
        lock_svc = LockService()
        if not lock_svc.exists():
            raise FileNotFoundError("No lock file found. Run 'arbor resolve' first.")
        packages = lock_svc.read()
        env_svc = EnvironmentService()
        if not env_svc.exists():
            env_svc.create(on_progress=on_progress)
        results = env_svc.install_packages(packages, on_progress=on_progress)
        return results
