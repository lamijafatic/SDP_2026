class ResolutionError(Exception):
    def __init__(self, message, unsatisfied=None):
        super().__init__(message)
        self.unsatisfied = unsatisfied or []

    def __str__(self):
        base = super().__str__()
        if self.unsatisfied:
            pkgs = ", ".join(self.unsatisfied)
            return f"{base}\n  Unsatisfied: {pkgs}"
        return base
