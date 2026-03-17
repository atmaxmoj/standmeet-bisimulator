"""Backwards compatibility — moved to pipeline.stages.filter."""
from engine.pipeline.stages.filter import *  # noqa: F401, F403
from engine.pipeline.stages.filter import should_keep, detect_windows  # noqa: F401
