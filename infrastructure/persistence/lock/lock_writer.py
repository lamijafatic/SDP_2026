import json
import os


def write_lock(solution, path="mypm.lock"):
    # pretvori solution u čist dict
    data = {pkg: str(ver) for pkg, ver in solution.items()}

    with open(path, "w") as f:
        json.dump(data, f, indent=2)