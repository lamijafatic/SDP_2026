from application.use_cases.resolve_dependencies import ResolveDependencies


class GenerateLockfile:
    def execute(self, strategy="sat"):
        use_case = ResolveDependencies(strategy=strategy)
        return use_case.execute()
