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

    # ── 1. Detect constraint files ───────────────────────────────────────────
    found = imp.detect(directory)
    found_pinned = imp.detect_pinned(directory)

    if not found and not found_pinned:
        print(warn("No supported dependency files found in this directory."))
        print()
        print(c("  Supported files:", DIM))
        for name, _ in imp.SUPPORTED:
            print(c(f"    {name}", DIM))
        return 1

    # ── 2. Parse constraint files ────────────────────────────────────────────
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

    # ── 3. Handle pinned version sources ────────────────────────────────────
    pinned_deps = {}
    if found_pinned:
        print(info("  Found pinned-version files (lockfile / pip freeze):"))
        for filename, path, _ in found_pinned:
            print(c(f"    {filename}", DIM))
        print()
        print(c("  These contain exact installed versions. How should they be used?", DIM))
        print(c("  [1] Keep exact  — import as ==version (re-resolve will use exact pins)", DIM))
        print(c("  [2] Use as floor — import as >=version (allows newer versions)", DIM))
        print(c("  [3] Ignore        — skip pinned files, use constraint files only", DIM))
        print()
        pin_choice = input("  Choice [1/2/3]: ").strip()

        if pin_choice in ("1", "2"):
            for filename, path, method in found_pinned:
                try:
                    parsed = getattr(imp, method)(path)
                    pinned_deps.update(parsed)
                except Exception as e:
                    print(warn(f"  Could not parse {filename}: {e}"))

            if pin_choice == "2":
                pinned_deps = imp.pinned_to_constraints(pinned_deps)

            # Pinned versions fill in packages not covered by constraint files
            for pkg, spec in pinned_deps.items():
                if pkg not in all_deps:
                    all_deps[pkg] = spec

            if pinned_deps:
                print()
                print(info(f"  Added {len(pinned_deps)} pinned package(s) as constraints."))
        print()

    if not all_deps:
        print(err("No dependencies could be parsed from the detected files."))
        return 1

    # ── 4. Show combined result ──────────────────────────────────────────────
    rows = []
    for pkg, constraint in sorted(all_deps.items()):
        source = "pinned" if pkg in pinned_deps and pkg not in {
            p for _, parsed, _ in parse_results for p in (parsed or {})
        } else "constraint"
        rows.append([pkg, constraint, source])

    print(info(f"  Total: {len(all_deps)} dependencies to import"))
    print()
    table(["Package", "Constraint", "Source"], rows)
    print()

    # ── 5. Handle existing mypm.toml ────────────────────────────────────────
    toml_path = os.path.join(directory, "mypm.toml")

    if os.path.exists(toml_path):
        old_dir = os.getcwd()
        os.chdir(directory)
        config = load_config()
        os.chdir(old_dir)
        existing_deps = config.get("dependencies", {})

        if existing_deps:
            print(warn(f"  mypm.toml already has {len(existing_deps)} dependency/ies."))
            print()
            print(c("  How should existing entries be handled?", DIM))
            print(c("  [1] Merge   — keep existing constraints, add new ones (existing wins)", DIM))
            print(c("  [2] Update  — keep existing packages, imported constraints win", DIM))
            print(c("  [3] Replace — overwrite everything with imported deps", DIM))
            print(c("  [4] Cancel", DIM))
            print()

            choice = input("  Choice [1/2/3/4]: ").strip()

            if choice == "4" or not choice:
                print(warn("  Import cancelled."))
                return 0
            elif choice == "1":
                merged = {**all_deps, **existing_deps}
            elif choice == "2":
                merged = {**existing_deps, **all_deps}
            elif choice == "3":
                merged = all_deps
            else:
                print(err("  Invalid choice."))
                return 1

            config["dependencies"] = merged
            old_dir = os.getcwd()
            os.chdir(directory)
            save_config(config)
            os.chdir(old_dir)
        else:
            config["dependencies"] = all_deps
            old_dir = os.getcwd()
            os.chdir(directory)
            save_config(config)
            os.chdir(old_dir)
    else:
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

    # ── 6. Summary ───────────────────────────────────────────────────────────
    divider()
    print()
    print(ok(f"  Imported {len(all_deps)} dependencies into mypm.toml."))
    print()
    print(c("  Next steps:", DIM))
    print(c("    arbor resolve               re-resolve with imported constraints", DIM))
    print(c("    arbor resolve --strategy hypergraph   use hypergraph resolver", DIM))
    print(c("    arbor install               install packages into venv", DIM))
    print(c("    arbor bot-setup             configure automated PR bot", DIM))
    print()
    return 0
