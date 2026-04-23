import os
from core.ui import section, ok, err, warn, info, table, c, DIM, bold, divider, confirm
from application.services.project_service import ProjectService
from application.services.import_service import ImportService
from infrastructure.persistence.toml.reader import load_config
from infrastructure.persistence.toml.writer import save_config


def run(args):
    section("Import Existing Project")

    directory = getattr(args, "path", None) or "."
    directory = os.path.abspath(directory)

    imp = ImportService()

    # ── 1. Detect files ──────────────────────────────────────────────────────
    found = imp.detect(directory)

    if not found:
        print(warn("No supported dependency files found in this directory."))
        print()
        print(c("  Supported files:", DIM))
        for name, _ in imp.SUPPORTED:
            print(c(f"    {name}", DIM))
        return 1

    print(info("  Found the following dependency files:"))
    for filename, path, _ in found:
        print(c(f"    {filename}", DIM))
    print()

    # ── 2. Parse each file ───────────────────────────────────────────────────
    all_deps = {}
    parse_results = []

    for filename, path, method in found:
        try:
            parsed = getattr(imp, method)(path)
            parse_results.append((filename, parsed, None))
            all_deps.update(parsed)
        except Exception as e:
            parse_results.append((filename, {}, str(e)))
            print(warn(f"  Could not parse {filename}: {e}"))

    if not all_deps:
        print(err("No dependencies could be parsed from the detected files."))
        return 1

    # ── 3. Show what was found ───────────────────────────────────────────────
    rows = []
    for filename, parsed, error in parse_results:
        if parsed:
            for pkg, constraint in parsed.items():
                rows.append([pkg, constraint, filename])
        elif error:
            rows.append(["(parse error)", "-", filename])

    print(info(f"  Found {len(all_deps)} dependencies:"))
    print()
    table(["Package", "Constraint", "Source"], rows)
    print()

    # ── 4. Handle existing mypm.toml ────────────────────────────────────────
    svc = ProjectService()
    toml_path = os.path.join(directory, "mypm.toml")

    if os.path.exists(toml_path):
        config = load_config()
        existing_deps = config.get("dependencies", {})

        if existing_deps:
            print(warn(f"  mypm.toml already has {len(existing_deps)} dependency/ies."))
            print()
            print(c("  How should existing entries be handled?", DIM))
            print(c("  [1] Merge  - keep existing, add new ones (existing constraints win)", DIM))
            print(c("  [2] Update - keep existing, add new ones (imported constraints win)", DIM))
            print(c("  [3] Replace - overwrite everything with imported deps", DIM))
            print(c("  [4] Cancel", DIM))
            print()

            choice = input("  Choice [1/2/3/4]: ").strip()

            if choice == "4" or not choice:
                print(warn("  Import cancelled."))
                return 0
            elif choice == "1":
                merged = {**all_deps, **existing_deps}  # existing wins
            elif choice == "2":
                merged = {**existing_deps, **all_deps}  # imported wins
            elif choice == "3":
                merged = all_deps
            else:
                print(err("  Invalid choice."))
                return 1

            config["dependencies"] = merged
            save_config(config)
        else:
            config["dependencies"] = all_deps
            save_config(config)
    else:
        # No mypm.toml yet - create one
        print(info("  No mypm.toml found, creating one."))
        project_name = os.path.basename(directory)
        config = {
            "project": {
                "name": project_name,
                "version": "0.1.0",
                "python": "3.11",
                "description": "",
            },
            "dependencies": all_deps,
        }
        old_dir = os.getcwd()
        os.chdir(directory)
        save_config(config)
        os.chdir(old_dir)

    # ── 5. Summary ───────────────────────────────────────────────────────────
    divider()
    print()
    print(ok(f"  Imported {len(all_deps)} dependencies into mypm.toml."))
    print()
    print(c("  Next steps:", DIM))
    print(c("    arbor resolve      generate lock file", DIM))
    print(c("    arbor install      install packages into venv", DIM))
    print(c("    arbor bot-setup    configure automated PR bot", DIM))
    print()
    return 0
