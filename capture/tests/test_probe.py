"""Tests for collector probe — discovering shell history files on the system.

Uses tmp_path to construct fake home directories with various shell history
layouts. Collectors accept home= parameter to override default paths.
"""

import pytest
from pathlib import Path


# ── Helper: create history files with realistic content ──


def write_zsh_extended(path: Path, commands: list[str]):
    """Write zsh extended history format: `: ts:dur;command`"""
    lines = [f": {1710428400 + i}:0;{cmd}" for i, cmd in enumerate(commands)]
    path.write_text("\n".join(lines) + "\n")


def write_zsh_plain(path: Path, commands: list[str]):
    path.write_text("\n".join(commands) + "\n")


def write_bash_history(path: Path, commands: list[str]):
    path.write_text("\n".join(commands) + "\n")


def write_fish_history(path: Path, commands: list[str]):
    """Write fish pseudo-YAML format."""
    entries = []
    for i, cmd in enumerate(commands):
        entries.append(f"- cmd: {cmd}")
        entries.append(f"  when: {1710428400 + i}")
    path.write_text("\n".join(entries) + "\n")


def write_powershell_history(path: Path, commands: list[str]):
    path.write_text("\n".join(commands) + "\n")


# ── Probe: zsh ──


class TestZshProbe:
    """Probe should find zsh history in various macOS configurations."""

    def test_standard_zsh_history(self, tmp_path):
        """~/.zsh_history exists → probe finds it."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        history = tmp_path / ".zsh_history"
        write_zsh_extended(history, ["git status", "npm test"])

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available
        assert str(history) in result.paths

    def test_session_files_only(self, tmp_path):
        """Only ~/.zsh_sessions/*.historynew exists (Apple Terminal)."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        sessions = tmp_path / ".zsh_sessions"
        sessions.mkdir()
        f1 = sessions / "ABC-123.historynew"
        write_zsh_extended(f1, ["echo hello"])
        f2 = sessions / "DEF-456.historynew"
        write_zsh_extended(f2, ["echo world"])

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available
        assert str(f1) in result.paths or str(f2) in result.paths

    def test_both_standard_and_sessions(self, tmp_path):
        """Both ~/.zsh_history and session files exist."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        history = tmp_path / ".zsh_history"
        write_zsh_extended(history, ["git status"])

        sessions = tmp_path / ".zsh_sessions"
        sessions.mkdir()
        session_file = sessions / "ABC-123.historynew"
        write_zsh_extended(session_file, ["echo hello"])

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available
        assert str(history) in result.paths
        assert str(session_file) in result.paths

    def test_closed_session_files_ignored(self, tmp_path):
        """~/.zsh_sessions/*.history (closed, no 'new') should not be watched."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        sessions = tmp_path / ".zsh_sessions"
        sessions.mkdir()
        # .history = closed session (already merged into ~/.zsh_history)
        closed = sessions / "ABC-123.history"
        write_zsh_extended(closed, ["old command"])

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        # Only closed sessions, no active ones — nothing useful to watch
        assert str(closed) not in result.paths

    def test_empty_home(self, tmp_path):
        """No zsh history anywhere → not available."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert not result.available

    def test_plain_format_detected(self, tmp_path):
        """Plain text zsh history (no EXTENDED_HISTORY) still works."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        history = tmp_path / ".zsh_history"
        write_zsh_plain(history, ["git push", "npm install"])

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available

    def test_empty_history_file(self, tmp_path):
        """History file exists but is empty → available but with warning."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        history = tmp_path / ".zsh_history"
        history.write_text("")

        collector = ZshHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available
        assert any("empty" in w.lower() for w in result.warnings)


# ── Probe: bash ──


class TestBashProbe:
    def test_standard_bash_history(self, tmp_path):
        from capture.collectors.shell_macos import BashHistoryCollector

        history = tmp_path / ".bash_history"
        write_bash_history(history, ["ls -la", "grep foo"])

        collector = BashHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available
        assert str(history) in result.paths

    def test_no_bash_history(self, tmp_path):
        from capture.collectors.shell_macos import BashHistoryCollector

        collector = BashHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert not result.available


# ── Probe: PowerShell (Windows) ──


class TestPowerShellProbe:
    def test_standard_path(self, tmp_path):
        from capture.collectors.shell_windows import PowerShellHistoryCollector

        ps_dir = tmp_path / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine"
        ps_dir.mkdir(parents=True)
        history = ps_dir / "ConsoleHost_history.txt"
        write_powershell_history(history, ["Get-Process", "Set-Location C:\\"])

        collector = PowerShellHistoryCollector(appdata=tmp_path)
        result = collector.probe()

        assert result.available
        assert str(history) in result.paths

    def test_no_powershell_history(self, tmp_path):
        from capture.collectors.shell_windows import PowerShellHistoryCollector

        collector = PowerShellHistoryCollector(appdata=tmp_path)
        result = collector.probe()

        assert not result.available

    def test_git_bash_history(self, tmp_path):
        """Git Bash on Windows stores history at ~\.bash_history"""
        from capture.collectors.shell_windows import GitBashHistoryCollector

        history = tmp_path / ".bash_history"
        write_bash_history(history, ["git log", "git diff"])

        collector = GitBashHistoryCollector(home=tmp_path)
        result = collector.probe()

        assert result.available
        assert str(history) in result.paths


# ── Probe: collect after probe ──


class TestProbeAndCollect:
    """After probe discovers files, collect should read from them."""

    def test_zsh_collect_from_session_file(self, tmp_path):
        """Collect reads from session files discovered by probe."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        sessions = tmp_path / ".zsh_sessions"
        sessions.mkdir()
        f = sessions / "ABC-123.historynew"
        write_zsh_extended(f, ["git status"])

        collector = ZshHistoryCollector(home=tmp_path)
        assert collector.probe().available

        # First collect: initialize
        collector.collect()

        # Append new command
        with open(f, "a") as fh:
            fh.write(": 1710428500:0;npm run build\n")

        result = collector.collect()
        assert "npm run build" in result

    def test_zsh_collect_from_standard_path(self, tmp_path):
        from capture.collectors.shell_macos import ZshHistoryCollector

        history = tmp_path / ".zsh_history"
        write_zsh_extended(history, ["git status"])

        collector = ZshHistoryCollector(home=tmp_path)
        collector.collect()  # init

        with open(history, "a") as f:
            f.write(": 1710428500:0;docker ps\n")

        result = collector.collect()
        assert "docker ps" in result

    def test_powershell_collect(self, tmp_path):
        from capture.collectors.shell_windows import PowerShellHistoryCollector

        ps_dir = tmp_path / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine"
        ps_dir.mkdir(parents=True)
        history = ps_dir / "ConsoleHost_history.txt"
        write_powershell_history(history, ["Get-Process"])

        collector = PowerShellHistoryCollector(appdata=tmp_path)
        collector.collect()  # init

        with open(history, "a") as f:
            f.write("Install-Module posh-git\n")

        result = collector.collect()
        assert "Install-Module posh-git" in result


# ── Probe report ──


class TestProbeReport:
    """The daemon prints a probe report on startup — verify format."""

    def test_summary_format_available(self):
        from capture.collectors.base import ProbeResult

        result = ProbeResult(
            available=True,
            source="zsh",
            description="found 2 history sources",
            paths=["/home/user/.zsh_history", "/home/user/.zsh_sessions/ABC.historynew"],
            warnings=["INC_APPEND_HISTORY is off"],
        )
        summary = result.summary()
        assert "[OK]" in summary
        assert "zsh" in summary
        assert ".zsh_history" in summary
        assert "INC_APPEND_HISTORY" in summary

    def test_summary_format_unavailable(self):
        from capture.collectors.base import ProbeResult

        result = ProbeResult(
            available=False,
            source="fish",
            description="no history file found",
        )
        summary = result.summary()
        assert "[SKIP]" in summary
        assert "fish" in summary
