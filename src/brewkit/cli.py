import subprocess

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import brew

out = Console()


def table(*cols: str) -> Table:
    return Table(*cols, header_style="bold cyan", box=None, pad_edge=False)

app = typer.Typer(no_args_is_help=True, add_completion=False)


def main():
    try:
        app()
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
