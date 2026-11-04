# brewkit

Small CLI around Homebrew. All data comes from `brew ... --json=v2`.

## Install

```sh
brew tap fedx21dragon/tap && brew install brewkit
```

From source (Python 3.12+), no pipx needed:

```sh
git clone https://github.com/fedx21dragon/brew-kit && cd brew-kit && ./install.sh
```

## Interactive menu

Run `brewkit` without arguments: ASCII banner, ↑↓ / Enter / `1`-`6` to pick, `Q` to quit.

## Commands

| Command | What it does |
|---|---|
| `brewkit search <term>` | Search formulae and casks |
| `brewkit list` | Installed packages with version |
| `brewkit info <name>` | Description, homepage, version |
| `brewkit outdated` | Packages with a newer version |
| `brewkit install <name>` | Preview, confirm, then install |
| `brewkit upgrade [name]` | Upgrade one or all. For casks, shows description and a changelog link first |

The changelog link is only shown when the cask's URL or homepage is a GitHub repo
(`https://github.com/<owner>/<repo>/releases`); Homebrew has no changelog field.

`brew search` has no JSON mode, so only package *names* are read from its output;
details are then fetched via `brew info --json=v2`.

## Development

```sh
.venv/bin/pytest
```

`brew` calls are mocked. Work on `feat/…` / `fix/…` branches, Conventional Commits.

## Release

1. Tag signed: `git tag -s vX.Y.Z -m vX.Y.Z && git push --tags`
2. Update `url` and `sha256` in `homebrew-tap/Formula/brewkit.rb`
   (`curl -sL <tarball-url> | shasum -a 256`), then commit in the tap repo.
3. Verify: `brew install --build-from-source fedx21dragon/tap/brewkit && brew test brewkit`.

## License

MIT
