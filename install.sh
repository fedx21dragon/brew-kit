#!/bin/sh
# Installs brewkit into ./.venv and links it to ~/.local/bin/brewkit
set -e
cd "$(dirname "$0")"
Y=$(printf '\033[33m'); G=$(printf '\033[32m'); D=$(printf '\033[2m'); R=$(printf '\033[0m')
printf '%s\n   🍺  brewkit installer\n%s\n' "$Y" "$R"
step() { printf '%s▸%s %s ' "$Y" "$R" "$1"; }
ok()   { printf '%s✔%s\n' "$G" "$R"; }
E=$(printf '\033[31m')
fail() { printf '%s✗%s\n%s\n' "$E" "$R" "$1"; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null || fail "Python 3.12+ is required (found: $(python3 --version 2>&1))"
step "Creating virtualenv";  L=$(python3 -m venv .venv 2>&1) || fail "$L"; ok
step "Installing";           L=$(.venv/bin/pip install -q -e . 2>&1) || fail "$L"; ok
step "Linking ~/.local/bin"; mkdir -p ~/.local/bin; ln -sf "$PWD/.venv/bin/brewkit" ~/.local/bin/brewkit; ok
printf '\n%sDone!%s Run %sbrewkit%s to start.\n' "$G" "$R" "$Y" "$R"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *)
  printf '%sAdd to ~/.zshrc:%s export PATH="$HOME/.local/bin:$PATH"\n' "$D" "$R";; esac
