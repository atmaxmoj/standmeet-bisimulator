"""Source plugin framework for Observer."""

from source_framework.plugin import SourcePlugin, ProbeResult
from source_framework.manifest import Manifest, load_manifest
from source_framework.client import EngineClient
from source_framework.runner import run_source

__all__ = [
    "SourcePlugin",
    "ProbeResult",
    "Manifest",
    "load_manifest",
    "EngineClient",
    "run_source",
]
