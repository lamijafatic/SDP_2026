from core.ui import section, warn, info, table, bold, c, DIM, Spinner
from application.services.resolution_service import ResolutionService
from application.services.project_service import ProjectService
from infrastructure.persistence.toml.reader import load_config


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    section("Dependency Resolution Explanation")

    data = load_config()
    deps = data.get("dependencies", {})
    if not deps:
        print(warn("No dependencies defined."))
        return 0

    sp = Spinner("Analyzing resolution...")
    sp.start()

    try:
        res_svc = ResolutionService()
        lines = res_svc.explain(deps)
        sp.stop(success=True, msg="Analysis complete")
    except Exception as e:
        sp.stop(success=False, msg="Analysis failed")
        print(c(f"  {e}", DIM))
        return 1

    print()
    rows = []
    for pkg, ver, reason in lines:
        rows.append([bold(pkg), c(ver, "\033[92m"), reason])

    table(["Package", "Selected", "Reason"], rows)
    print()
    print(c("  The SAT solver encodes all constraints as CNF clauses and finds", DIM))
    print(c("  a consistent truth assignment where all constraints are satisfied.", DIM))
    return 0
