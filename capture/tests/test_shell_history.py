"""Tests for shell history parsing and collection."""

from unittest.mock import patch, MagicMock

from capture.collectors.shell_macos import (
    _parse_zsh_line,
    _is_noise,
    _signal_zsh_flush,
    ZshHistoryCollector,
)


class TestParseZshLine:
    def test_extended_format(self):
        assert _parse_zsh_line(": 1710428400:0;git status") == "git status"

    def test_extended_format_with_semicolons(self):
        assert _parse_zsh_line(": 1710428400:0;echo 'hello; world'") == "echo 'hello; world'"

    def test_plain_format(self):
        assert _parse_zsh_line("npm install") == "npm install"

    def test_empty_line(self):
        assert _parse_zsh_line("") == ""

    def test_whitespace_only(self):
        assert _parse_zsh_line("   ") == ""


class TestIsNoise:
    def test_trivial_commands(self):
        assert _is_noise("ls") is True
        assert _is_noise("cd /tmp") is True
        assert _is_noise("pwd") is True
        assert _is_noise("clear") is True
        assert _is_noise("exit") is True

    def test_real_commands(self):
        assert _is_noise("git push origin main") is False
        assert _is_noise("npm run build") is False
        assert _is_noise("docker compose up -d") is False
        assert _is_noise("python -m pytest") is False


class TestZshHistoryCollector:
    def test_first_run_returns_empty(self, tmp_path):
        history = tmp_path / ".zsh_history"
        history.write_text(": 1710428400:0;git status\n: 1710428401:0;npm test\n")

        collector = ZshHistoryCollector()
        collector._path = history

        # First run: initialize position, return nothing
        result = collector.collect()
        assert result == []

    def test_new_commands_returned(self, tmp_path):
        history = tmp_path / ".zsh_history"
        history.write_text(": 1710428400:0;git status\n")

        collector = ZshHistoryCollector()
        collector._path = history
        collector.collect()  # init

        # Append new commands
        with open(history, "a") as f:
            f.write(": 1710428402:0;docker compose up -d\n")
            f.write(": 1710428403:0;npm run build\n")

        result = collector.collect()
        assert result == ["docker compose up -d", "npm run build"]

    def test_noise_filtered(self, tmp_path):
        history = tmp_path / ".zsh_history"
        history.write_text(": 1710428400:0;git status\n")

        collector = ZshHistoryCollector()
        collector._path = history
        collector.collect()  # init

        with open(history, "a") as f:
            f.write(": 1710428402:0;ls\n")
            f.write(": 1710428403:0;cd /tmp\n")
            f.write(": 1710428404:0;npm test\n")

        result = collector.collect()
        assert result == ["npm test"]

    def test_no_new_data(self, tmp_path):
        history = tmp_path / ".zsh_history"
        history.write_text(": 1710428400:0;git status\n")

        collector = ZshHistoryCollector()
        collector._path = history
        collector.collect()  # init

        result = collector.collect()
        assert result == []

    def test_missing_file(self, tmp_path):
        collector = ZshHistoryCollector()
        collector._path = tmp_path / "nonexistent"
        assert collector.available() is False
        assert collector.collect() == []

    def test_periodic_reread_even_if_size_unchanged(self, tmp_path):
        """After 30 cycles, collector re-reads file even if size is same."""
        history = tmp_path / ".zsh_history"
        history.write_text(": 1710428400:0;git status\n")

        collector = ZshHistoryCollector()
        collector._path = history
        collector.collect()  # init

        # Simulate 29 cycles with no change — should all return empty
        for _ in range(29):
            assert collector.collect() == []

        # 30th cycle should re-read (even though size hasn't changed)
        # No new lines, so still empty, but it doesn't skip the read
        result = collector.collect()
        assert result == []

    def test_flush_signal_called_periodically(self, tmp_path):
        """SIGUSR1 should be sent every 10 cycles to trigger zsh flush."""
        history = tmp_path / ".zsh_history"
        history.write_text(": 1710428400:0;git status\n")

        collector = ZshHistoryCollector()
        collector._path = history
        collector.collect()  # init (counter=1)

        with patch("capture.collectors.shell_macos._signal_zsh_flush") as mock_flush:
            # Run 9 more cycles (counter 2-10), flush should fire at 10
            for i in range(9):
                collector.collect()

            assert mock_flush.call_count == 1


class TestSignalZshFlush:
    def test_sends_sigusr1_to_zsh_pids(self):
        result = MagicMock()
        result.stdout = "1234\n5678\n"

        with patch("subprocess.run", return_value=result), \
             patch("os.getpid", return_value=9999), \
             patch("os.kill") as mock_kill:
            _signal_zsh_flush()
            assert mock_kill.call_count == 2

    def test_skips_own_pid(self):
        result = MagicMock()
        result.stdout = "1234\n9999\n"

        with patch("subprocess.run", return_value=result), \
             patch("os.getpid", return_value=9999), \
             patch("os.kill") as mock_kill:
            _signal_zsh_flush()
            assert mock_kill.call_count == 1  # only 1234, not 9999

    def test_handles_pgrep_failure(self):
        with patch("subprocess.run", side_effect=Exception("no pgrep")):
            # Should not raise
            _signal_zsh_flush()
