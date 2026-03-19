# Probe Tests — Docker Shell Environment

Standalone Docker test environment for verifying shell history probe against
real shells. The container installs zsh, bash, fish, and PowerShell, generates
genuine history files via `setup_shells.sh`, then runs `test_probe_docker.py`
to verify the probe discovers and reads them correctly.

## Usage

```bash
# From repo root:
docker build -t probe-test -f capture/tests/docker/Dockerfile .
docker run --rm probe-test
```

## Shell environments inside the container

| Shell | History path | Format |
|-------|-------------|--------|
| zsh | `~/.zsh_history` | extended (`: ts:dur;cmd`) |
| zsh sessions | `~/.zsh_sessions/*.historynew` | same (simulates Apple Terminal) |
| bash | `~/.bash_history` | plain text |
| fish | `~/.local/share/fish/fish_history` | pseudo-YAML (`- cmd: ...\n  when: ...`) |
| PowerShell | `~/.local/share/powershell/PSReadLine/ConsoleHost_history.txt` | plain text |

## Files

- `Dockerfile` — installs shells, generates history, runs tests
- `setup_shells.sh` — creates real history files from actual shell invocations
- `../test_probe_docker.py` — test cases (only runs inside this Docker environment)
