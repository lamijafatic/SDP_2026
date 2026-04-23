
## Overview

Arbor is a command-line package manager for Python projects. It uses a SAT solver for deterministic dependency resolution, manages virtual environments, tracks locked versions, and includes an automated GitHub PR bot that opens pull requests when your dependencies have updates available.

---

## How It Works

1. The user adds dependencies with version constraints
2. The system collects available versions for each package from PyPI
3. A dependency graph is built
4. Invalid versions are filtered out
5. A compatible set of versions is selected using a SAT solver
6. The result is written to a lock file
7. Packages are installed into a virtual environment

---

## Dependency Resolution Logic

The dependency resolution problem is modeled using a formal mathematical approach based on hypergraphs.

In this model:

- Packages and their versions are represented as nodes
- Dependencies are represented as relationships between sets of nodes (hyperedges)
- Constraints define which combinations of versions are valid or invalid

This allows the dependency system to be described as a set of logical conditions over package-version combinations.

The model is then transformed into a Boolean formulation, where:

- Each (package, version) pair is represented as a variable
- Constraints are translated into logical expressions
- Invalid combinations are explicitly forbidden

This formulation is converted into a satisfiability problem, which allows the system to efficiently determine whether a valid set of versions exists. The solver efficiently explores the solution space and returns a combination of package versions that satisfies all constraints, avoiding naive search and enabling handling of more complex dependency structures in a structured and scalable way.

---

## Installation

Clone the repository and install in editable mode:

    git clone https://github.com/lamijafatic/SDP_2026
    cd SDP_2026
    pip install -e .

After installation, the arbor command is available globally.

---

## Quick Start — New Project

    arbor init myproject        create a new project
    arbor add requests          add a dependency
    arbor resolve               calculate compatible versions
    arbor install               install packages into a virtual environment
    arbor status                verify everything is working

## Quick Start — Existing Project

    cd your-existing-project
    arbor import .              detect and import existing dependency files
    arbor resolve               generate a lock file
    arbor install               install packages
    arbor bot-setup             configure the PR update bot

---

## Commands

### Project Commands

arbor init [name] [--python VERSION]

    Initializes a new Arbor project in the current directory. Creates mypm.toml with project
    metadata. Optionally accepts a project name and Python version. If no name is given,
    it prompts interactively.

arbor info

    Shows project metadata from mypm.toml: name, version, Python version, description,
    number of dependencies, and whether a lock file and virtual environment exist.

arbor status

    Full health overview of the project. Shows project info, all declared dependencies
    with their constraints, lock file status, virtual environment status, and a summary
    of installed packages.

arbor doctor

    Runs a health check and reports any issues: missing mypm.toml, missing lock file,
    missing virtual environment, mismatch between locked and installed packages,
    missing Python version.

arbor import [path]

    Scans an existing project directory for dependency files and imports them into mypm.toml.
    Supports: requirements.txt, requirements.in, pyproject.toml (PEP 621 and Poetry formats),
    setup.cfg, setup.py, and Pipfile. Shows a table of all found dependencies with their
    source file. If mypm.toml already has dependencies, offers four options:
      1  Merge   - keep existing constraints, add new ones
      2  Update  - imported constraints win on conflict
      3  Replace - overwrite everything with imported deps
      4  Cancel
    If no mypm.toml exists, creates one from scratch.

### Dependency Commands

arbor add PACKAGE [CONSTRAINT]

    Adds a dependency to mypm.toml. Constraint is optional and defaults to >=0.1.
    Examples:
        arbor add numpy
        arbor add requests ">=2.28"
        arbor add pandas ">=1.5,<3.0"

arbor remove PACKAGE

    Removes a dependency from mypm.toml.

arbor show

    Lists all declared dependencies with their version constraints.

arbor update [PACKAGE]

    Updates a dependency to the latest compatible version. If no package is given,
    updates all dependencies.

### Resolution Commands

arbor resolve [--strategy sat|backtracking]

    Resolves all declared dependencies using a SAT solver (default) or backtracking
    algorithm. Finds a set of package versions that satisfy all constraints simultaneously.
    Writes the result to mypm.lock. Must be run after adding, removing, or updating
    dependencies.

arbor lock

    Regenerates the lock file. Equivalent to arbor resolve.

arbor explain

    Shows which version was selected for each package and why — which constraint
    drove the decision.

arbor conflicts

    Lists known conflicts in the package registry — packages that cannot be installed
    together.

### Environment Commands

arbor install [--dry-run]

    Installs all packages from the lock file into a local virtual environment (.venv).
    Use --dry-run to see what would be installed without actually installing anything.

arbor sync

    Syncs the virtual environment with the current lock file. Installs missing packages
    and removes packages that are no longer in the lock file.

arbor clean

    Removes the virtual environment completely. Use arbor install to recreate it.

arbor build

    Builds a distribution package (source distribution and wheel) from the current project.

### Package Registry Commands

arbor search QUERY

    Searches available packages in the registry by name or keyword.

arbor versions PACKAGE

    Shows all available versions for a given package.

arbor list

    Lists all packages available in the registry.

### Debug Commands

arbor graph

    Visualizes the full dependency graph: which packages depend on which, and what
    version constraints exist between them.

arbor trace

    Traces the resolution process step by step, showing how the SAT solver or
    backtracking algorithm arrived at its decisions.

arbor dump

    Dumps the complete internal project state as JSON. Useful for debugging or
    inspecting the raw data structures.

### Bot Commands

The bot module automates dependency updates by checking PyPI for newer versions and
opening GitHub pull requests. Each update gets its own PR with a description of what
changed, the version delta, and a risk level classification.

arbor bot-setup

    Interactive setup wizard. Run this first before using any other bot commands.
    It guides you through:
      - Confirming or entering your GitHub repository (auto-detected from git remote)
      - Setting your GitHub personal access token (also reads GITHUB_TOKEN env var)
      - Choosing the base branch for pull requests
      - Selecting which update types to watch: patch, minor, major
      - Enabling or disabling update grouping (one PR per package vs one PR for all)
      - Enabling or disabling auto-merge for low-risk updates
      - Setting an ignore list for packages you never want auto-updated
    All settings are saved to the [bot] section of mypm.toml.

arbor bot-check

    Checks PyPI for available updates without creating any branches or pull requests.
    Shows a table of packages with newer versions, their current and latest versions,
    the update type (patch, minor, or major), and the risk level.

arbor bot-run [--dry-run]

    Creates GitHub pull requests for all available dependency updates. For each update it:
    creates a git branch, modifies mypm.toml and mypm.lock, commits the change, pushes
    the branch, and opens a PR on GitHub with a full description and labels.
    Use --dry-run to preview what would happen without pushing or creating PRs.
    Before running, it validates all prerequisites and shows a clear error message if
    anything is missing (git repo, remote, lock file, bot configuration, GitHub token).

arbor bot-config [--show] [--init]

    Shows or initializes the bot configuration stored in mypm.toml.
    Use --show to display current settings (token is masked).
    Use --init to add a default [bot] section if one does not exist yet.

---

## Bot Configuration

Bot settings are stored in the [bot] section of mypm.toml (managed by arbor bot-setup):

    github_repo     your GitHub repository in owner/repo format (e.g. username/myproject)
    github_token    personal access token with repo scope (or set GITHUB_TOKEN env var)
    base_branch     branch that PRs will target, usually main
    update_types    list of update types to process: patch, minor, major
    group_updates   true to combine all updates into one PR, false for one PR each
    auto_merge      true to enable GitHub auto-merge on created PRs
    labels          true to apply colored labels to PRs
    ignore          list of package names to never auto-update

### GitHub Token Setup

The bot requires a GitHub personal access token with repo scope. You can set it in three ways:

1. Run arbor bot-setup and enter the token when prompted (saved to mypm.toml)
2. Set the environment variable: export GITHUB_TOKEN=your_token_here
3. Add it permanently to your shell profile (~/.zshrc or ~/.bashrc)

To generate a token: GitHub Settings > Developer settings > Personal access tokens >
Generate new token. Required scope: repo.

### Risk Levels

The bot classifies updates by risk level based on semantic versioning:

    patch update    e.g. 2.28.0 -> 2.28.3    low risk
    minor update    e.g. 2.28.0 -> 2.31.0    medium risk
    major update    e.g. 2.28.0 -> 3.0.0     high risk

---

## Project Files

    mypm.toml       project configuration, dependencies, and bot settings
    mypm.lock       locked package versions (generated by arbor resolve)
    .venv/          virtual environment (generated by arbor install)

---

## Complete Workflow Examples

New project from scratch:

    arbor init myapp
    arbor add requests ">=2.28"
    arbor add numpy ">=1.24"
    arbor resolve
    arbor install
    arbor bot-setup
    arbor bot-check
    arbor bot-run

Existing project onboarding:

    cd existing-project
    arbor import .
    arbor resolve
    arbor install
    arbor bot-setup
    arbor bot-run --dry-run
    arbor bot-run
