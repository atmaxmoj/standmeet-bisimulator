#!/bin/sh
set -e

HOME=/home/testuser

# ── zsh: standard history (extended format) ──
# Contains commands that ALSO appear in session files (simulating merge)
printf ': 1710428400:0;git status\n: 1710428401:0;docker compose up -d\n: 1710428402:0;npm run build\n' \
  > "$HOME/.zsh_history"

# ── zsh: Apple Terminal-style session files ──
mkdir -p "$HOME/.zsh_sessions"

# Active session 1 — has commands that overlap with .zsh_history
printf ': 1710428400:0;git status\n: 1710428401:0;docker compose up -d\n: 1710428403:0;vim README.md\n' \
  > "$HOME/.zsh_sessions/SESS-001.historynew"

# Active session 2 — different terminal tab, different commands
printf ': 1710428410:0;cargo build\n: 1710428411:0;cargo test\n' \
  > "$HOME/.zsh_sessions/SESS-002.historynew"

# Active session 3 — empty (just opened a tab, nothing typed yet)
touch "$HOME/.zsh_sessions/SESS-003.historynew"

# Closed session — already merged into .zsh_history, should be ignored
printf ': 1710428300:0;old closed command\n: 1710428301:0;another old one\n' \
  > "$HOME/.zsh_sessions/SESS-OLD.history"

# Session metadata files (Apple creates these, should be ignored)
echo 'echo Restored session: "Thu Mar 14 2024"' > "$HOME/.zsh_sessions/SESS-001.session"

# ── bash: overlapping commands with zsh ──
# Some users switch between bash and zsh — same commands may appear in both
cat > "$HOME/.bash_history" <<'BASH'
git status
docker compose up -d
python -m pytest
make deploy
npm run build
BASH

# ── fish ──
mkdir -p "$HOME/.local/share/fish"
cat > "$HOME/.local/share/fish/fish_history" <<'FISH'
- cmd: kubectl get pods
  when: 1710428400
- cmd: docker logs -f app
  when: 1710428401
- cmd: ssh user@server
  when: 1710428402
FISH

# ── PowerShell (file only) ──
mkdir -p "$HOME/.local/share/powershell/PSReadLine"
printf 'Get-Process\nInstall-Module posh-git\nSet-Location C:\\Users\n' \
  > "$HOME/.local/share/powershell/PSReadLine/ConsoleHost_history.txt"

# ══════════════════════════════════════════════════════════════════════
# CHAOS: simulate a messy system with leftover files from migrations,
# OS upgrades, shell switches, config changes, etc.
# The live event stream goes through ONE file; everything else is stale.
# ══════════════════════════════════════════════════════════════════════
mkdir -p "$HOME/chaos"

# User was on bash, switched to zsh, then enabled sessions.
# Left behind: stale .bash_history, stale .zsh_history, old sessions
printf 'echo old-bash-era\nmake old-build\n' \
  > "$HOME/chaos/.bash_history"
printf ': 1700000000:0;echo old-zsh-no-sessions\n: 1700000001:0;npm old-install\n' \
  > "$HOME/chaos/.zsh_history"

mkdir -p "$HOME/chaos/.zsh_sessions"
# Stale closed sessions from months ago
printf ': 1700000100:0;ancient-session-cmd\n' \
  > "$HOME/chaos/.zsh_sessions/OLD-AAA.history"
printf ': 1700000200:0;another-ancient-cmd\n' \
  > "$HOME/chaos/.zsh_sessions/OLD-BBB.history"
# Apple metadata
echo 'echo Restored session: "Mon Jan 1 2024"' > "$HOME/chaos/.zsh_sessions/OLD-AAA.session"

# THE ONE ACTIVE SESSION — this is where events actually flow
printf ': 1710428500:0;echo current-session\n' \
  > "$HOME/chaos/.zsh_sessions/CURRENT.historynew"

echo "=== Shell history setup complete ==="
echo "zsh_history:    $(wc -l < "$HOME/.zsh_history") lines"
echo "zsh_sessions:   $(ls "$HOME/.zsh_sessions/"*.historynew 2>/dev/null | wc -l) active, $(ls "$HOME/.zsh_sessions/"*.history 2>/dev/null | wc -l) closed"
echo "bash_history:   $(wc -l < "$HOME/.bash_history") lines"
echo "fish_history:   $(wc -l < "$HOME/.local/share/fish/fish_history") lines"
echo "ps_history:     $(wc -l < "$HOME/.local/share/powershell/PSReadLine/ConsoleHost_history.txt") lines"
