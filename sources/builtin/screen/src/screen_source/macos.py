"""macOS screen capture backend — placeholder.

Backend code currently lives in capture/src/capture/backends/macos.py.
It provides: get_all_displays, capture_display, hash_image, ocr_image,
compress_image, get_frontmost_app.

Will be migrated into this module in Phase 2, removing the dependency on
the capture package. The ScreenSource plugin currently imports these
functions via `from capture.backends import ...`.
"""
