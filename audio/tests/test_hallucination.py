"""Tests for whisper hallucination detection."""

from audio.transcriber import is_hallucination


class TestIsHallucination:
    def test_repetitive_you(self):
        result = {
            "text": "You You You You You You You You You You You",
            "language": "en",
            "language_probability": 0.8,
            "segments": [],
        }
        assert is_hallucination(result) is True

    def test_repetitive_thank_you(self):
        result = {
            "text": "Thank you. Thank you. Thank you. Thank you. Thank you.",
            "language": "en",
            "language_probability": 0.9,
            "segments": [],
        }
        # "you." and "Thank" each appear 5/10 = 50%, but "Thank" is 5/10 = 50%
        # This shouldn't trigger since no single word > 60%
        # Actually: words = ["thank", "you.", "thank", "you.", ...]
        # "thank" = 5/10 = 50%, "you." = 5/10 = 50% → neither > 60%, so NOT hallucination
        assert is_hallucination(result) is False

    def test_repetitive_single_word(self):
        result = {
            "text": "the the the the the the the the the the",
            "language": "en",
            "language_probability": 0.7,
            "segments": [],
        }
        assert is_hallucination(result) is True

    def test_low_language_probability(self):
        result = {
            "text": "Some random text here",
            "language": "en",
            "language_probability": 0.3,
            "segments": [],
        }
        assert is_hallucination(result) is True

    def test_normal_speech(self):
        result = {
            "text": "So I was thinking about the project and we should probably refactor the database layer",
            "language": "en",
            "language_probability": 0.95,
            "segments": [],
        }
        assert is_hallucination(result) is False

    def test_short_text_not_hallucination(self):
        result = {
            "text": "OK yes",
            "language": "en",
            "language_probability": 0.8,
            "segments": [],
        }
        # Only 2 words, repetition check requires >= 3
        assert is_hallucination(result) is False

    def test_empty_text(self):
        result = {
            "text": "",
            "language": "en",
            "language_probability": 0.5,
            "segments": [],
        }
        assert is_hallucination(result) is False

    def test_chinese_repetitive(self):
        result = {
            "text": "谢谢 谢谢 谢谢 谢谢 谢谢 谢谢 谢谢",
            "language": "zh",
            "language_probability": 0.7,
            "segments": [],
        }
        assert is_hallucination(result) is True

    def test_borderline_60_percent(self):
        # 6 out of 10 words = exactly 60%, should NOT trigger (> 0.6, not >=)
        result = {
            "text": "hello hello hello hello hello hello world foo bar baz",
            "language": "en",
            "language_probability": 0.9,
            "segments": [],
        }
        assert is_hallucination(result) is False

    def test_just_over_60_percent(self):
        # 7 out of 10 words = 70% → hallucination
        result = {
            "text": "hello hello hello hello hello hello hello world foo bar",
            "language": "en",
            "language_probability": 0.9,
            "segments": [],
        }
        assert is_hallucination(result) is True
