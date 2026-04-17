import sys
import time
import threading
import os

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_DARK = "\033[40m"


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(text, *codes):
    if not _supports_color():
        return str(text)
    return "".join(codes) + str(text) + RESET


def ok(msg):
    return c(f"  {msg}", BRIGHT_GREEN)


def err(msg):
    return c(f"  ✘  {msg}", BRIGHT_RED)


def warn(msg):
    return c(f"  ⚠  {msg}", BRIGHT_YELLOW)


def info(msg):
    return c(f"  →  {msg}", BRIGHT_CYAN)


def dim_text(msg):
    return c(msg, DIM)


def bold(msg):
    return c(msg, BOLD)


def header(msg):
    return c(msg, BOLD, BRIGHT_WHITE)


def banner():
    logo = [
        "",
        c("  ╔══════════════════════════════════════╗", BRIGHT_CYAN),
        c("  ║", BRIGHT_CYAN) + c("         ⚡  ARBOR  v0.1.0  ⚡         ", BOLD, BRIGHT_WHITE) + c("║", BRIGHT_CYAN),
        c("  ║", BRIGHT_CYAN) + c("      Python Package Manager           ", DIM) + c("║", BRIGHT_CYAN),
        c("  ║", BRIGHT_CYAN) + c("      SAT-Based Dependency Resolver    ", DIM) + c("║", BRIGHT_CYAN),
        c("  ╚══════════════════════════════════════╝", BRIGHT_CYAN),
        "",
    ]
    print("\n".join(logo))


def section(title):
    width = 44
    bar = "─" * width
    print()
    print(c(f"  {title}", BOLD, BRIGHT_WHITE))
    print(c(f"  {bar}", BLUE))


def success_box(title, lines):
    width = max(len(title), max((len(l) for l in lines), default=0)) + 4
    border = "═" * width
    print()
    print(c(f"  ╔{border}╗", BRIGHT_GREEN))
    print(c(f"  ║", BRIGHT_GREEN) + c(f"  {title:<{width-2}}  ", BOLD, BRIGHT_WHITE) + c("║", BRIGHT_GREEN))
    print(c(f"  ╠{border}╣", BRIGHT_GREEN))
    for line in lines:
        print(c(f"  ║", BRIGHT_GREEN) + f"  {line:<{width-2}}  " + c("║", BRIGHT_GREEN))
    print(c(f"  ╚{border}╝", BRIGHT_GREEN))
    print()


def table(headers, rows):
    if not rows:
        print(c("  (no items)", DIM))
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    top = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
    mid = "╞" + "╪".join("═" * (w + 2) for w in col_widths) + "╡"
    sep = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
    bot = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"

    def row_str(cells, color=None):
        parts = []
        for i, cell in enumerate(cells):
            w = col_widths[i] if i < len(col_widths) else 10
            txt = f" {str(cell):<{w}} "
            if color:
                txt = c(txt, color)
            parts.append(txt)
        return c("│", BLUE) + c("│", BLUE).join(parts) + c("│", BLUE)

    print()
    print(c(f"  {top}", BLUE))
    header_cells = [c(f" {h:<{col_widths[i]}} ", BOLD) for i, h in enumerate(headers)]
    print("  " + c("│", BLUE) + c("│", BLUE).join(header_cells) + c("│", BLUE))
    print(c(f"  {mid}", BLUE))
    for i, row in enumerate(rows):
        print(f"  {row_str(row)}")
        if i < len(rows) - 1:
            pass
    print(c(f"  {bot}", BLUE))
    print()


def tree(root_name, deps_dict):
    """Print ASCII dependency tree."""
    print()
    print(c(f"  {root_name}", BOLD, BRIGHT_WHITE))
    items = list(deps_dict.items())
    for idx, (pkg, sub_deps) in enumerate(items):
        is_last = idx == len(items) - 1
        connector = "└──" if is_last else "├──"
        print(c(f"  {connector} ", BLUE) + c(pkg, BRIGHT_WHITE))
        for sidx, (sub, constraint) in enumerate(sub_deps):
            is_sub_last = sidx == len(sub_deps) - 1
            sub_connector = "    └──" if is_sub_last else "    ├──"
            if not is_last:
                sub_connector = "│   " + ("└──" if is_sub_last else "├──")
            print(c(f"  {sub_connector} ", BLUE) + c(sub, CYAN) + c(f" {constraint}", DIM))
        if not sub_deps:
            prefix = "    " if is_last else "│   "
            print(c(f"  {prefix}└── ", BLUE) + c("(no deps)", DIM))
    print()


class Spinner:
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message="Working..."):
        self.message = message
        self.running = False
        self._thread = None

    def _spin(self):
        i = 0
        while self.running:
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r  {c(frame, BRIGHT_CYAN)}  {self.message}   ")
            sys.stdout.flush()
            time.sleep(0.08)
            i += 1

    def start(self, message=None):
        if message:
            self.message = message
        self.running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def stop(self, success=True, msg=None):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
        label = msg or self.message
        sys.stdout.write("\r" + " " * (len(label) + 12) + "\r")
        sys.stdout.flush()
        if success:
            print(ok(label))
        else:
            print(err(label))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


def progress_bar(current, total, label="", width=28):
    pct = current / total if total > 0 else 0
    filled = int(width * pct)
    bar = c("█" * filled, BRIGHT_GREEN) + c("░" * (width - filled), DIM)
    pct_str = c(f"{pct * 100:5.1f}%", BOLD)
    sys.stdout.write(f"\r  [{bar}] {pct_str}  {label:<30}")
    sys.stdout.flush()
    if current >= total:
        print()


def confirm(prompt, default=True):
    default_str = "[Y/n]" if default else "[y/N]"
    try:
        ans = input(c(f"  ? {prompt} {default_str}: ", BRIGHT_YELLOW)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not ans:
        return default
    return ans in ("y", "yes")


def prompt_input(msg, default=None):
    default_hint = c(f" [{default}]", DIM) if default else ""
    try:
        val = input(c(f"  > {msg}", BRIGHT_CYAN) + default_hint + ": ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return val if val else default


def divider():
    print(c("  " + "─" * 44, DIM))
