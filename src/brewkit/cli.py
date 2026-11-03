import subprocess

import typer

from . import brew

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
    for e in brew.search(term):
        typer.echo(f"{e['name']} ({e['kind']})  {e['desc'] or ''}")


@app.command("list")
def list_():
    """Installed packages with version."""
    for e in brew.installed():
        typer.echo(f"{e['name']} {e['installed']}")


@app.command()
def info(name: str):
    """Description and homepage."""
    e = brew.info([name])[0]
    typer.echo(f"{e['name']} ({e['kind']}) {e['version']}\n{e['desc'] or ''}\n{e['homepage'] or ''}")


@app.command()
def outdated():
    """Outdated packages."""
    for o in brew.outdated():
        typer.echo(f"{o['name']} {o['installed']} -> {o['current']}")


@app.command()
def upgrade(name: str = typer.Argument(None)):
    """Upgrade one or all; casks show description and changelog link first."""
    targets = [name] if name else [o["name"] for o in brew.outdated() if o["kind"] == "cask"]
    for e in brew.info(targets) if targets else []:
        if e["kind"] == "cask":
            typer.echo(f"{e['name']}: {e['desc'] or ''}")
            if link := brew.changelog_url(e):
                typer.echo(f"  Changelog: {link}")
    brew.upgrade(name)
