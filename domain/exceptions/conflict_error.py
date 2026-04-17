class ConflictError(Exception):
    def __init__(self, pkg1, ver1, pkg2, ver2, reason=""):
        self.pkg1 = pkg1
        self.ver1 = ver1
        self.pkg2 = pkg2
        self.ver2 = ver2
        msg = f"Conflict: {pkg1}@{ver1} is incompatible with {pkg2}@{ver2}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
