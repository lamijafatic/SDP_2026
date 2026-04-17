from core.ui import section, warn, info, tree, bold, c, DIM, Spinner
from application.services.project_service import ProjectService
from infrastructure.persistence.toml.reader import load_config
from infrastructure.repository.smart_repo import SmartRepository
from application.services.graph_service import GraphService
from infrastructure.persistence.lock.lock_reader import read_lock
import os


def run(args):
    svc = ProjectService()
    if not svc.is_initialized():
        print(warn("No project found. Run 'arbor init' first."))
        return 1

    data = load_config()
    deps = data.get("dependencies", {})

    if not deps:
        print(warn("No dependencies to visualize."))
        return 0

    section("Dependency Graph")

    sp = Spinner("Building dependency graph...")
    sp.start()

    repo = SmartRepository()
    service = GraphService(repo)
    graph = service.build_graph(deps)
    sp.stop(success=True, msg="Graph built")

    locked = {}
    if os.path.exists("mypm.lock"):
        locked = read_lock()

    project_name = data.get("project", {}).get("name", "project")

    dep_tree = {}
    for pkg_name, dep_obj in graph.dependencies.items():
        candidates = graph.get_candidates(pkg_name)
        if not candidates:
            continue
        resolved = locked.get(pkg_name, str(candidates[-1]) if candidates else "?")

        from domain.models.version import Version
        try:
            resolved_v = Version(resolved)
            subdeps_list = [
                (sub_name, str(sub_constraint))
                for sub_name, sub_constraint in graph.get_dependencies(pkg_name, resolved_v)
            ]
        except Exception:
            subdeps_list = []

        dep_tree[f"{pkg_name} @ {resolved}"] = subdeps_list

    tree(project_name, dep_tree)

    total_pkgs = len(graph.dependencies)
    direct_pkgs = len(deps)
    transitive = total_pkgs - direct_pkgs
    print(c(f"  Direct: {direct_pkgs}  |  Transitive: {transitive}  |  Total: {total_pkgs}", DIM))
    return 0
