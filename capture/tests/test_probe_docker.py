"""Probe tests against real shell environments (run inside Docker).

The container has a deliberately messy setup:
- ~/.zsh_history AND ~/.zsh_sessions/ both exist (session mode)
- Same commands appear in both .zsh_history and .historynew files
- Multiple active sessions (different terminal tabs)
- One empty session file (just opened, nothing typed)
- Closed sessions (.history) that should be ignored
- .session metadata files that should be ignored
- bash history overlaps with zsh (user switches shells)

Run:
    docker build -t probe-test -f capture/tests/docker/Dockerfile .
    docker run --rm probe-test
"""

from pathlib import Path

HOME = Path.home()  # /home/testuser inside Docker


# ── zsh: session mode with messy state ──


class TestZshSessionModeReal:
    """zsh_history + zsh_sessions + overlapping commands."""

    def test_session_mode_activated(self):
        """Both .zsh_history and .zsh_sessions/ exist → session mode."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        collector = ZshHistoryCollector(home=HOME)
        result = collector.probe()

        assert result.available
        assert "session" in result.description

    def test_standard_history_skipped(self):
        """~/.zsh_history should NOT be in paths — it's a merge target."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=HOME).probe()
        assert not any(p.endswith(".zsh_history") for p in result.paths), \
            f".zsh_history should be skipped: {result.paths}"

    def test_only_active_sessions_watched(self):
        """Only .historynew files, not .history or .session files."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=HOME).probe()

        for p in result.paths:
            assert p.endswith(".historynew"), f"unexpected path: {p}"

        # We set up 3 active sessions (SESS-001, SESS-002, SESS-003)
        assert len(result.paths) == 3

    def test_closed_session_not_watched(self):
        """SESS-OLD.history should not appear."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=HOME).probe()
        assert not any("SESS-OLD" in p for p in result.paths)

    def test_session_metadata_ignored(self):
        """.session files (Apple restore scripts) should not appear."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=HOME).probe()
        assert not any(p.endswith(".session") for p in result.paths)

    def test_no_duplicates_across_history_and_sessions(self):
        """Commands in both .zsh_history and .historynew should appear only once.
        Since session mode skips .zsh_history entirely, this is guaranteed."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        collector = ZshHistoryCollector(home=HOME)
        collector.collect()  # init all trackers

        # Append "git status" to both — but only session file should be read
        zsh_history = HOME / ".zsh_history"
        session_file = HOME / ".zsh_sessions" / "SESS-001.historynew"

        with open(zsh_history, "a") as f:
            f.write(": 1999999999:0;overlapping-cmd\n")
        with open(session_file, "a") as f:
            f.write(": 1999999999:0;overlapping-cmd\n")

        result = collector.collect()
        assert result.count("overlapping-cmd") == 1

    def test_multiple_sessions_independent_streams(self):
        """Commands appended to different session files all get collected."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        collector = ZshHistoryCollector(home=HOME)
        collector.collect()  # init

        s1 = HOME / ".zsh_sessions" / "SESS-001.historynew"
        s2 = HOME / ".zsh_sessions" / "SESS-002.historynew"

        with open(s1, "a") as f:
            f.write(": 1999999999:0;from-tab-1\n")
        with open(s2, "a") as f:
            f.write(": 1999999999:0;from-tab-2\n")

        result = collector.collect()
        assert "from-tab-1" in result
        assert "from-tab-2" in result

    def test_empty_session_file_no_crash(self):
        """SESS-003.historynew is empty — should not crash or emit events."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        collector = ZshHistoryCollector(home=HOME)
        result = collector.collect()  # init — should not crash

        # Empty file contributes nothing
        empty = HOME / ".zsh_sessions" / "SESS-003.historynew"
        assert empty.exists()
        assert empty.stat().st_size == 0

    def test_session_close_midway(self):
        """Simulate a session closing: rename .historynew → .history.
        Collector should stop getting events from it."""
        from capture.collectors.shell_macos import ZshHistoryCollector
        import shutil

        # Work on a copy so we don't mess up other tests
        s2_orig = HOME / ".zsh_sessions" / "SESS-002.historynew"
        s2_copy = HOME / ".zsh_sessions" / "SESS-CLOSING.historynew"
        shutil.copy2(s2_orig, s2_copy)

        collector = ZshHistoryCollector(home=HOME)
        collector.collect()  # init — picks up SESS-CLOSING

        with open(s2_copy, "a") as f:
            f.write(": 1999999999:0;before-close\n")

        result = collector.collect()
        assert "before-close" in result

        # Session closes
        closed = HOME / ".zsh_sessions" / "SESS-CLOSING.history"
        s2_copy.rename(closed)

        # Should not crash, should not re-emit
        result2 = collector.collect()
        assert "before-close" not in result2


# ── chaos: messy filesystem, one live stream ──


class TestChaosReal:
    """Simulate a user who migrated bash → zsh → zsh with sessions.
    Filesystem has stale history from every era. Only one .historynew
    is actually receiving new events."""

    CHAOS = HOME / "chaos"

    def test_probe_finds_only_active_session(self):
        """Among all the mess, probe should only watch CURRENT.historynew."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=self.CHAOS).probe()
        assert result.available

        # Only the one active .historynew
        assert len(result.paths) == 1
        assert "CURRENT.historynew" in result.paths[0]

    def test_stale_zsh_history_not_watched(self):
        """Old .zsh_history from before sessions were enabled — skipped."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=self.CHAOS).probe()
        assert not any(p.endswith(".zsh_history") for p in result.paths)

    def test_closed_sessions_not_watched(self):
        """OLD-AAA.history, OLD-BBB.history — ancient, closed, ignored."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        result = ZshHistoryCollector(home=self.CHAOS).probe()
        assert not any("OLD-" in p for p in result.paths)

    def test_events_only_from_active_stream(self):
        """Append to stale files + active file. Only active one produces events."""
        from capture.collectors.shell_macos import ZshHistoryCollector

        collector = ZshHistoryCollector(home=self.CHAOS)
        collector.collect()  # init

        # Write to stale .zsh_history (should be ignored)
        with open(self.CHAOS / ".zsh_history", "a") as f:
            f.write(": 1999999999:0;stale-zsh-cmd\n")

        # Write to closed session (should be ignored)
        with open(self.CHAOS / ".zsh_sessions" / "OLD-AAA.history", "a") as f:
            f.write(": 1999999999:0;stale-session-cmd\n")

        # Write to the ONE active session
        with open(self.CHAOS / ".zsh_sessions" / "CURRENT.historynew", "a") as f:
            f.write(": 1999999999:0;live-event\n")

        result = collector.collect()
        assert "live-event" in result
        assert "stale-zsh-cmd" not in result
        assert "stale-session-cmd" not in result

    def test_stale_bash_independent(self):
        """Old bash history exists but bash collector handles it separately."""
        from capture.collectors.shell_macos import BashHistoryCollector

        collector = BashHistoryCollector(home=self.CHAOS)
        result = collector.probe()

        # bash history exists from the bash era — it's valid for bash collector
        assert result.available

        collector.collect()  # init
        with open(self.CHAOS / ".bash_history", "a") as f:
            f.write("new-bash-cmd\n")
        result = collector.collect()
        assert "new-bash-cmd" in result

    def test_total_files_vs_watched(self):
        """Many history files on disk, but very few actually watched."""
        from capture.collectors.shell_macos import ZshHistoryCollector
        import os

        # Count all history-looking files in chaos/
        all_files = []
        for root, _, files in os.walk(self.CHAOS):
            for f in files:
                if "history" in f.lower():
                    all_files.append(os.path.join(root, f))

        result = ZshHistoryCollector(home=self.CHAOS).probe()

        # Many files exist, but only 1 is watched
        assert len(all_files) >= 5, f"expected messy state, got {all_files}"
        assert len(result.paths) == 1


# ── bash + zsh overlap ──


class TestCrossShellOverlap:
    """bash and zsh histories contain overlapping commands."""

    def test_bash_and_zsh_both_available(self):
        from capture.collectors.shell_macos import ZshHistoryCollector, BashHistoryCollector

        zsh = ZshHistoryCollector(home=HOME).probe()
        bash = BashHistoryCollector(home=HOME).probe()

        assert zsh.available
        assert bash.available

    def test_same_command_in_both_collected_independently(self):
        """Both collectors are independent — same command from both is OK.
        Dedup across shells is not the collector's job."""
        from capture.collectors.shell_macos import ZshHistoryCollector, BashHistoryCollector

        zsh_c = ZshHistoryCollector(home=HOME)
        bash_c = BashHistoryCollector(home=HOME)
        zsh_c.collect()  # init
        bash_c.collect()  # init

        # "git status" is already in both histories from setup
        # Append fresh duplicate to both
        s1 = HOME / ".zsh_sessions" / "SESS-001.historynew"
        with open(s1, "a") as f:
            f.write(": 1999999999:0;shared-cmd-test\n")
        with open(HOME / ".bash_history", "a") as f:
            f.write("shared-cmd-test\n")

        zsh_result = zsh_c.collect()
        bash_result = bash_c.collect()

        # Each collector reports it once
        assert "shared-cmd-test" in zsh_result
        assert "shared-cmd-test" in bash_result


# ── fish ──


class TestFishReal:
    def test_history_exists_and_valid(self):
        path = HOME / ".local" / "share" / "fish" / "fish_history"
        assert path.exists()
        content = path.read_text()
        assert "- cmd:" in content
        assert "when:" in content


# ── PowerShell ──


class TestPowerShellReal:
    def test_history_exists_and_valid(self):
        path = HOME / ".local" / "share" / "powershell" / "PSReadLine" / "ConsoleHost_history.txt"
        assert path.exists()
        content = path.read_text()
        assert "Get-Process" in content


# ── Probe report ──


class TestProbeReportReal:
    def test_full_report(self):
        from capture.collectors.shell_macos import ZshHistoryCollector, BashHistoryCollector

        lines = []
        for c in [ZshHistoryCollector(home=HOME), BashHistoryCollector(home=HOME)]:
            result = c.probe()
            lines.append(result.summary())

        report = "\n".join(lines)
        assert "[OK]" in report
        assert "session" in report  # zsh should say "session mode"
