"""Source runner — loads manifest, imports entrypoint, probes, and runs."""

import importlib
import logging
import os
import sys
from pathlib import Path

from source_framework.client import EngineClient
from source_framework.manifest import Manifest, load_manifest
from source_framework.plugin import SourcePlugin

logger = logging.getLogger(__name__)


def _import_plugin_class(manifest: Manifest) -> type[SourcePlugin]:
    """Import the SourcePlugin subclass from the manifest's entrypoint.

    Entrypoint format: "module_name:ClassName"
    e.g. "screen_source:ScreenSource"
    """
    entrypoint = manifest.entrypoint
    if not entrypoint or ":" not in entrypoint:
        raise ValueError(
            f"Invalid entrypoint '{entrypoint}' in manifest '{manifest.name}'. "
            f"Expected format: 'module_name:ClassName'"
        )

    module_name, class_name = entrypoint.split(":", 1)

    # Add the source's src/ directory to sys.path so imports work
    src_dir = manifest.source_dir / "src"
    if src_dir.is_dir():
        src_path = str(src_dir)
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)

    if not (isinstance(cls, type) and issubclass(cls, SourcePlugin)):
        raise TypeError(
            f"{entrypoint} resolved to {cls}, which is not a SourcePlugin subclass"
        )

    return cls


def load_and_probe(source_dir: Path) -> tuple[Manifest, SourcePlugin | None]:
    """Load manifest and probe the source.

    Returns (manifest, plugin_instance) if probe succeeds, or
    (manifest, None) if the source is not available.
    """
    manifest = load_manifest(source_dir)

    if not manifest.supports_current_platform():
        logger.info(
            "[SKIP] %s: platform %s not in %s",
            manifest.name, sys.platform, manifest.platform,
        )
        return manifest, None

    cls = _import_plugin_class(manifest)
    plugin = cls()
    result = plugin.probe()

    logger.info(result.summary())

    if not result.available:
        return manifest, None

    return manifest, plugin


def run_source(source_dir: str | Path, engine_url: str | None = None):
    """Load a source from its directory and run it.

    Args:
        source_dir: Path to the source directory containing manifest.json.
        engine_url: Engine API base URL. Defaults to ENGINE_URL env var.
    """
    source_dir = Path(source_dir)
    engine_url = engine_url or os.environ.get("ENGINE_URL", "http://localhost:5001")

    manifest, plugin = load_and_probe(source_dir)

    if plugin is None:
        logger.warning("Source '%s' is not available, exiting.", manifest.name)
        return

    client = EngineClient(base_url=engine_url, source_name=manifest.name)
    config = manifest.get_default_config()

    # Override defaults with env vars: SOURCE_<NAME>_<KEY>=value
    prefix = f"SOURCE_{manifest.name.upper()}_"
    for key in config:
        env_key = prefix + key.upper()
        env_val = os.environ.get(env_key)
        if env_val is not None:
            # Coerce to the same type as the default
            default = config[key]
            if isinstance(default, bool):
                config[key] = env_val.lower() in ("1", "true", "yes")
            elif isinstance(default, int):
                config[key] = int(env_val)
            elif isinstance(default, float):
                config[key] = float(env_val)
            else:
                config[key] = env_val

    logger.info(
        "Starting source '%s' (version %s) → %s",
        manifest.name, manifest.version, engine_url,
    )

    plugin.start(client, config)
