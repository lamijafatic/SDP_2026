import os
from infrastructure.persistence.lock.lock_writer import write_lock
from infrastructure.persistence.lock.lock_reader import read_lock

LOCK_FILE = "mypm.lock"


class LockService:
    def exists(self):
        return os.path.exists(LOCK_FILE)

    def write(self, solution: dict):
        write_lock(solution)

    def read(self) -> dict:
        if not self.exists():
            return {}
        return read_lock()

    def is_in_sync(self, current_deps: dict, repo) -> bool:
        if not self.exists():
            return False
        locked = self.read()
        locked_pkgs = set(locked.keys())
        dep_pkgs = set(current_deps.keys())
        return locked_pkgs >= dep_pkgs

    def diff(self, current_solution: dict) -> dict:
        locked = self.read()
        added = {k: v for k, v in current_solution.items() if k not in locked}
        removed = {k: v for k, v in locked.items() if k not in current_solution}
        changed = {
            k: (locked[k], current_solution[k])
            for k in locked
            if k in current_solution and locked[k] != current_solution[k]
        }
        return {"added": added, "removed": removed, "changed": changed}
