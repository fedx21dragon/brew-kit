import os
from importlib import metadata
import subprocess
import sys
import termios
import tty

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import brew

out = Console()


def table(*cols: str) -> Table:
    return Table(*cols, header_style="bold cyan", box=None, pad_edge=False)


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


def main():
    try:
        app()
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130)
    except subprocess.CalledProcessError as e:
        typer.echo(f"brew failed (exit {e.returncode}): {' '.join(e.cmd[:3])}", err=True)
        raise SystemExit(1)


@app.command()
def search(term: str):
    """Search formulae and casks."""
    t = table("Name", "Type", "Description")
    for e in brew.search(term):
        t.add_row(f"[bold]{e['name']}[/]", "[magenta]cask[/]" if e["kind"] == "cask" else "formula", e["desc"] or "")
    out.print(t)


@app.command("list")
def list_():
    """Installed packages with version."""
    t = table("Name", "Version")
    for e in brew.installed():
        t.add_row(f"[bold]{e['name']}[/]", f"[green]{e['installed']}[/]")
    out.print(t)


@app.command()
def info(name: str):
    """Description and homepage."""
    e = brew.info([name])[0]
    body = f"{e['desc'] or ''}\n[blue underline]{e['homepage'] or ''}[/]"
    out.print(Panel(body, title=f"[bold]{e['name']}[/] {e['version']} ({e['kind']})", expand=False))


@app.command()
def outdated():
    """Outdated packages."""
    t = table("Name", "Installed", "Latest")
    for o in brew.outdated():
        t.add_row(f"[bold]{o['name']}[/]", f"[red]{o['installed']}[/]", f"[green]{o['current']}[/]")
    out.print(t if t.row_count else "[green]Everything is up to date.[/]")


@app.command()
def upgrade(name: str = typer.Argument(None)):
    """Upgrade one or all; casks show description and changelog link first."""
    targets = [name] if name else [o["name"] for o in brew.outdated() if o["kind"] == "cask"]
    for e in brew.info(targets) if targets else []:
        if e["kind"] == "cask":
            out.print(f"[bold]{e['name']}[/]: {e['desc'] or ''}")
            if link := brew.changelog_url(e):
                out.print(f"  Changelog: [blue underline]{link}[/]")
    brew.upgrade(name)


@app.command()
def install(name: str):
    """Preview a package, confirm, then install."""
    info(name)
    if Confirm.ask(f"[bold cyan]➤[/] Install [bold]{name}[/]?", default=False):
        brew.install(name)
        out.print(f"🍺 [green]{name} installed.[/]")


BANNER = r"""
 _                              _      _  _
| |__   _ __   ___  __      __ | | __ (_)| |_
| '_ \ | '__| / _ \ \ \ /\ / / | |/ / | || __|
| |_) || |   |  __/  \ V  V /  |   <  | || |_
|_.__/ |_|    \___|   \_/\_/   |_|\_\ |_| \__|
"""


def ask(label: str, **kw) -> str:
    """Prompt; re-asks on empty input unless a default is given."""
    while True:
        v = Prompt.ask(f"[bold cyan]➤[/] {label}", show_default=False, **kw).strip()
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
    n = ask("Package to upgrade [dim](empty = all)[/]", default="")
    if Confirm.ask(f"[bold cyan]➤[/] Upgrade {n or 'everything'}?", default=False):
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
        if c == b"\x1b":
            c += os.read(fd, 2)
        return {b"\x1b[A": "up", b"\x1b[B": "down", b"\n": "enter", b"\r": "enter"}.get(c, c.decode(errors="ignore"))
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)


def _flush():
    """Drop stray keypresses (key repeat, \r\n) so they can't answer the next prompt."""
    if sys.stdin.isatty():
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)


def _draw(sel: int, first: bool):
    if not first:
        out.file.write(f"\x1b[{len(ITEMS) + 3}A")  # jump back over the previous menu
    for i, (name, desc, _) in enumerate(ITEMS):
        arrow, style = ("➤", "bold cyan") if i == sel else (" ", "white")
        out.print(f"[{style}]{arrow} {i + 1}. {name:<10} {desc}[/]", end="\x1b[K\n")
    out.print("", end="\x1b[K\n")
    out.print("[dim]↑↓ | Enter | 1-6 Jump | Q Quit[/]", end="\x1b[K\n")
    out.print("", end="\x1b[K\n")


def menu():
    sel = 0
    while True:
        out.print(BANNER, style="green", highlight=False, markup=False)
        out.print("[bold blue]Homebrew, made friendly.[/]  [green]Search, install, upgrade.[/]\n")
        first = True
        while True:
            _draw(sel, first)
            first = False
            k = _key()
            if k in ("q", "Q", "\x03"):
                out.print("[dim]Cheers 🍻[/]")
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
        out.print()
        _flush()
        try:
            ITEMS[sel][2]()
        except subprocess.CalledProcessError as e:
            out.print(f"[red]brew failed (exit {e.returncode})[/]")
        _flush()
        Prompt.ask("\n[dim]Press Enter to go back[/]", default="", show_default=False)
        out.clear()
