"""Thin subprocess wrapper around brew. Always --json=v2, never parse text."""
import json
import re
import subprocess


def _run(*args: str) -> str:
    return subprocess.run(
        ["brew", *args], check=True, capture_output=True, text=True
    ).stdout


def _json(*args: str) -> dict:
    return json.loads(_run(*args, "--json=v2"))


SEARCH_LIMIT = 30


def search(term: str) -> list[dict]:
    # `brew search` has no JSON mode and only prints names; take the names,
    # then get the real data from `brew info --json=v2`.
    names = []
    for kind in ("--formulae", "--casks"):
        out = subprocess.run(
            ["brew", "search", kind, term], capture_output=True, text=True
        ).stdout
        names += [n for n in out.split() if "==>" not in n]
    return info(names[:SEARCH_LIMIT]) if names else []


def info(names: list[str]) -> list[dict]:
    """Return unified entries: {name, kind, desc, homepage, version, installed, url}."""
    data = _json("info", *names)
    out = [_formula(f) for f in data["formulae"]]
    out += [_cask(c) for c in data["casks"]]
    return out


def _formula(f: dict) -> dict:
    inst = f.get("installed") or []
    return dict(name=f["name"], kind="formula", desc=f.get("desc"),
                homepage=f.get("homepage"), version=f["versions"]["stable"],
                installed=inst[0]["version"] if inst else None, url=None)


def _cask(c: dict) -> dict:
    return dict(name=c["token"], kind="cask", desc=c.get("desc"),
                homepage=c.get("homepage"), version=c.get("version"),
                installed=c.get("installed"), url=c.get("url"))


def installed() -> list[dict]:
    data = _json("info", "--installed")
    return [_formula(f) for f in data["formulae"]] + [_cask(c) for c in data["casks"]]


def _joined(v) -> str:
    # casks report installed_versions as a string, formulae as a list
    return v if isinstance(v, str) else ", ".join(v)


def outdated() -> list[dict]:
    d = _json("outdated")
    return [dict(name=x["name"], kind=kind, current=x["current_version"],
                 installed=_joined(x["installed_versions"]))
            for kind, key in (("formula", "formulae"), ("cask", "casks")) for x in d[key]]


def upgrade(name: str | None) -> None:
    subprocess.run(["brew", "upgrade", *([name] if name else [])], check=True)


def install(name: str) -> None:
    subprocess.run(["brew", "install", name], check=True)


def changelog_url(cask: dict) -> str | None:
    """Only if the cask points at a GitHub repo; None otherwise."""
    for u in (cask.get("url"), cask.get("homepage")):
        m = re.match(r"https://github\.com/([^/]+/[^/]+)", u or "")
        if m:
            return f"https://github.com/{m[1]}/releases"
    return None
