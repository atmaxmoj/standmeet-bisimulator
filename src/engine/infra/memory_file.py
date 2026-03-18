"""Backwards compatibility — all symbols moved to engine.storage.memory_file."""

from engine.storage.memory_file import (  # noqa: F401
    write_playbook, write_routine, delete_playbook, MEMORY_DIR,
)
