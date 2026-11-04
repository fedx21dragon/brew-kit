import os
import select
import subprocess
import sys
import termios
import tty
from importlib import metadata

import typer
from rich.console import Console
from rich.markup import escape as esc
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import brew

out = Console()

# One palette for menu and commands (Catppuccin-ish, matches the Mole look).
ACCENT = "#7fdbca"  # turquoise: selection, headers, prompts
GREEN = "#a6e3a1"   # banner, versions, success
BLUE = "#89b4fa"    # links
CASK = "#cba6f7"    # casks
ERR = "#f38ba8"     # errors, outdated versions
DIM = "grey50"


def table(*cols: str) -> Table:
    return Table(*cols, header_style=f"bold {ACCENT}", box=None, pad_edge=False, padding=(0, 3, 0, 0))


def busy():
    return out.status(f"[{DIM}]Asking brew…[/]", spinner="dots", spinner_style=ACCENT)


def kind(k: str) -> str:
    return f"[{CASK}]cask[/]" if k == "cask" else f"[{DIM}]formula[/]"


app = typer.Typer(add_completion=False)


def _version(show: bool):
    if show:
        typer.echo(metadata.version("brewkit"))
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def home(ctx: typer.Context, version: bool = typer.Option(False, "--version", callback=_version, is_eager=True)):
    """Homebrew, but friendlier. Run without a command for the interactive menu."""
    if ctx.invoked_subcommand is None:
        menu()


def _brew_error(e: Exception) -> str:
    if isinstance(e, FileNotFoundError):
        return "brew not found. Install Homebrew first: https://brew.sh"
    return f"brew failed (exit {e.returncode}): {' '.join(e.cmd[:3])}"


def main():
    try:
        app()
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        Console(stderr=True).print(f"[{ERR}]✗ {esc(_brew_error(e))}[/]")
        raise SystemExit(1)


@app.command()
def search(term: str):
    """Search formulae and casks."""
    t = table("Name", "Type", "Description")
    with busy():
        found = brew.search(term)
    for e in found:
        t.add_row(f"[bold]{esc(e['name'])}[/]", kind(e["kind"]), esc(e["desc"] or ""))
    out.print(t if t.row_count else f"[{DIM}]Nothing found for '{esc(term)}'.[/]")


@app.command("list")
def list_():
    """Installed packages with version."""
    t = table("Name", "Version")
    with busy():
        pkgs = brew.installed()
    for e in pkgs:
        t.add_row(f"[bold]{esc(e['name'])}[/]", f"[{GREEN}]{esc(str(e['installed']))}[/]")
    out.print(t)


def _show(name: str) -> list[dict]:
    """Print an info panel per match (a name can be both a formula and a cask)."""
    with busy():
        entries = brew.info([name])
    for e in entries:
        body = f"{esc(e['desc'] or '')}\n[{BLUE} underline]{esc(e['homepage'] or '')}[/]"
        title = f"[bold]{esc(e['name'])}[/] [{GREEN}]{esc(str(e['version']))}[/] {kind(e['kind'])}"
        out.print(Panel(body, title=title, title_align="left", border_style=ACCENT, expand=False))
    if not entries:
        out.print(f"[{DIM}]Nothing found for '{esc(name)}'.[/]")
    return entries


@app.command()
def info(name: str):
    """Description and homepage."""
    _show(name)


@app.command()
def outdated():
    """Outdated packages."""
    t = table("Name", "Installed", "Latest")
    with busy():
        old = brew.outdated()
    for o in old:
        t.add_row(f"[bold]{esc(o['name'])}[/]", f"[{ERR}]{esc(o['installed'])}[/]", f"[{GREEN}]{esc(o['current'])}[/]")
    out.print(t if t.row_count else f"[{GREEN}]✔ Everything is up to date.[/]")


@app.command()
def upgrade(name: str = typer.Argument(None)):
    """Upgrade one or all; casks show description and changelog link first."""
    try:  # the preview is a nicety: if it fails, still upgrade
        with busy():
            targets = [name] if name else [o["name"] for o in brew.outdated() if o["kind"] == "cask"]
            previews = brew.info(targets) if targets else []
    except subprocess.CalledProcessError:
        previews = []
    for e in previews:
        if e["kind"] == "cask":
            out.print(f"[bold]{esc(e['name'])}[/] {kind('cask')}  {esc(e['desc'] or '')}")
            if link := brew.changelog_url(e):
                out.print(f"  Changelog [{BLUE} underline]{esc(link)}[/]")
    brew.upgrade(name)


@app.command()
def install(name: str):
    """Preview a package, confirm, then install."""
    entries = _show(name)
    if not entries:
        return
    chosen = None
    if len({e["kind"] for e in entries}) > 1:  # same name as formula and cask
        chosen = ask("Install as", choices=["formula", "cask"], default="formula")
    if Confirm.ask(f"[bold {ACCENT}]➤[/] Install [bold]{esc(name)}[/]?", default=False):
        brew.install(name, chosen)
        out.print(f"[{GREEN}]✔ {esc(name)} installed.[/]")


BANNER = r"""
 _                              _      _  _
| |__   _ __   ___  __      __ | | __ (_)| |_
| '_ \ | '__| / _ \ \ \ /\ / / | |/ / | || __|
| |_) || |   |  __/  \ V  V /  |   <  | || |_
|_.__/ |_|    \___|   \_/\_/   |_|\_\ |_| \__|
""".strip("\n").split("\n")
# Tagline rows sit next to the bottom of the banner, like in Mole.
SIDE = {3: f"[{BLUE} underline]https://github.com/fedx21dragon/brew-kit[/]", 4: f"[{GREEN}]Homebrew, made friendly.[/]"}


def banner():
    w = max(len(line) for line in BANNER)
    for i, line in enumerate(BANNER):
        out.print(f"[{GREEN}]{line.ljust(w)}[/]  {SIDE.get(i, '')}", highlight=False)
    out.print()


def ask(label: str, **kw) -> str:
    """Prompt; re-asks on empty input unless a default is given."""
    while True:
        v = Prompt.ask(f"[bold {ACCENT}]➤[/] {label}", show_default=False, **kw).strip()
        if v or "default" in kw:
            return v


ITEMS = [
    ("Search", "Find formulae and casks", lambda: search(ask("Search term"))),
    ("List", "Installed packages", lambda: list_()),
    ("Info", "Description and homepage", lambda: info(ask("Name"))),
    ("Install", "Preview, confirm, install", lambda: install(ask("Name"))),
    ("Outdated", "What has a newer version", lambda: outdated()),
    ("Upgrade", "Update one package or all", lambda: _upgrade_flow()),
]


def _upgrade_flow():
    outdated()
    n = ask(f"Package to upgrade [{DIM}](empty = all)[/]", default="")
    if Confirm.ask(f"[bold {ACCENT}]➤[/] Upgrade {n or 'everything'}?", default=False):
        upgrade(n or None)


def _key() -> str:
    """One keypress: 'up', 'down', 'enter', or the character."""
    if not sys.stdin.isatty():  # piped input (tests)
        return sys.stdin.read(1) or "q"
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd, termios.TCSANOW)
        c = os.read(fd, 1)  # raw fd read: no hidden Python-side buffer that swallows/replays keys
        if c == b"\x1b" and select.select([fd], [], [], 0.05)[0]:  # bare Esc has no follow-up bytes
            c += os.read(fd, 2)
        return {b"\x1b[A": "up", b"\x1b[B": "down", b"\n": "enter", b"\r": "enter"}.get(c, c.decode(errors="ignore"))
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)


def _flush():
    """Drop stray keypresses (key repeat, \r\n) so they can't answer the next prompt."""
    if sys.stdin.isatty():
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)


def _cursor(show: bool):
    if out.is_terminal:
        out.file.write("\x1b[?25h" if show else "\x1b[?25l")


MENU_LINES = len(ITEMS) + 2  # items + blank + footer


def _draw(sel: int, first: bool):
    if not first:
        out.file.write(f"\x1b[{MENU_LINES}A")  # jump back over the previous menu
    for i, (name, desc, _) in enumerate(ITEMS):
        row = f"{i + 1}. {name:<10}  {desc}"
        out.print(f"[bold {ACCENT}]➤ {row}[/]" if i == sel else f"  {row}", end="\x1b[K\n")
    out.print("", end="\x1b[K\n")
    out.print(f"[{DIM}]↑↓  |  Enter  |  1-{len(ITEMS)} Jump  |  Q Quit[/]", end="\x1b[K\n")


def menu():
    try:
        _menu()
    except KeyboardInterrupt:
        out.print(f"\n[{DIM}]Cheers 🍻[/]")


def _menu():
    sel = 0
    while True:
        banner()
        first = True
        _cursor(False)
        try:
            while True:
                _draw(sel, first)
                first = False
                k = _key()
                if k in ("q", "Q"):
                    out.print(f"[{DIM}]Cheers 🍻[/]")
                    return
                if k == "up":
                    sel = (sel - 1) % len(ITEMS)
                elif k == "down":
                    sel = (sel + 1) % len(ITEMS)
                elif k.isdigit() and 1 <= int(k) <= len(ITEMS):
                    sel = int(k) - 1
                    break
                elif k == "enter":
                    break
        finally:
            _cursor(True)
        out.print()
        _flush()
        try:
            ITEMS[sel][2]()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            out.print(f"[{ERR}]✗ {esc(_brew_error(e))}[/]")
        _flush()
        Prompt.ask(f"\n[{DIM}]Press Enter to go back[/]", default="", show_default=False)
        out.clear()
