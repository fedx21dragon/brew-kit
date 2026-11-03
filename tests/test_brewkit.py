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
    assert "bar 1.1" in r.output and "foo 1.0" in r.output


def test_upgrade_cask_shows_changelog():
    out = {"formulae": [], "casks": [{"name": "foo", "current_version": "2.0",
                                       "installed_versions": ["1.0"]}]}
    def run(*a):
        return json.dumps(out if a[0] == "outdated" else {"formulae": [], "casks": [CASK]})
    with patch.object(brew, "_run", run), patch.object(brew, "upgrade") as up:
        r = CliRunner().invoke(app, ["upgrade"])
    assert "A tool" in r.output and "acme/foo/releases" in r.output
    up.assert_called_once_with(None)
