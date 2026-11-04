import json
from unittest.mock import patch

from typer.testing import CliRunner

from brewkit import brew
from brewkit.cli import app

CASK = {"token": "foo", "desc": "A tool", "homepage": "https://foo.dev",
        "version": "2.0", "installed": "1.0", "url": "https://github.com/acme/foo/dl.dmg"}
FORMULA = {"name": "bar", "desc": "Lib", "homepage": "https://bar.org",
           "versions": {"stable": "1.2"}, "installed": [{"version": "1.1"}]}


def fake_run(*args):
    return json.dumps({"formulae": [FORMULA], "casks": [CASK]})


def test_changelog_only_with_source():
    assert brew.changelog_url({"url": "https://github.com/acme/foo/x", "homepage": None}) \
        == "https://github.com/acme/foo/releases"
    assert brew.changelog_url({"url": "https://x.com/a", "homepage": "https://foo.dev"}) is None


def test_list():
    with patch.object(brew, "_run", fake_run):
        r = CliRunner().invoke(app, ["list"])
    assert "bar  " in r.output and "1.1" in r.output and "foo" in r.output and "1.0" in r.output


def test_upgrade_cask_shows_changelog():
    out = {"formulae": [], "casks": [{"name": "foo", "current_version": "2.0",
                                       "installed_versions": ["1.0"]}]}
    def run(*a):
        return json.dumps(out if a[0] == "outdated" else {"formulae": [], "casks": [CASK]})
    with patch.object(brew, "_run", run), patch.object(brew, "upgrade") as up:
        r = CliRunner().invoke(app, ["upgrade"])
    assert "A tool" in r.output and "acme/foo/releases" in r.output
    up.assert_called_once_with(None)


def test_brew_failure_is_short_error(monkeypatch):
    import subprocess, pytest
    from brewkit import cli
    def boom(*a): raise subprocess.CalledProcessError(1, ["brew", "info", "x"])
    monkeypatch.setattr(brew, "_run", boom)
    monkeypatch.setattr("sys.argv", ["brewkit", "info", "x"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 1


def test_install_declined_does_not_install():
    with patch.object(brew, "_run", fake_run), patch.object(brew, "install") as ins:
        CliRunner().invoke(app, ["install", "foo"], input="n\n")
    ins.assert_not_called()


def test_menu_quit():
    r = CliRunner().invoke(app, [], input="q")
    assert "Homebrew, made friendly" in r.output and r.exit_code == 0


def test_outdated_handles_string_and_list_versions():
    d = {"formulae": [{"name": "a", "current_version": "2", "installed_versions": ["1", "0.9"]}],
         "casks": [{"name": "b", "current_version": "2", "installed_versions": "1"}]}
    with patch.object(brew, "_run", lambda *a: json.dumps(d)):
        r = brew.outdated()
    assert [o["installed"] for o in r] == ["1, 0.9", "1"]


def test_search_is_capped():
    names = " ".join(f"p{i}" for i in range(100))
    seen = {}
    def fake_info(n):
        seen["n"] = n
        return []
    with patch("subprocess.run") as run, patch.object(brew, "info", fake_info):
        run.return_value.stdout = names
        brew.search("p")
    assert len(seen["n"]) == brew.SEARCH_LIMIT


def test_version_flag():
    r = CliRunner().invoke(app, ["--version"])
    assert r.exit_code == 0 and r.output.strip()[0].isdigit()


def test_info_output():
    with patch.object(brew, "_run", fake_run):
        r = CliRunner().invoke(app, ["info", "bar"])
    assert "bar" in r.output and "bar.org" in r.output
