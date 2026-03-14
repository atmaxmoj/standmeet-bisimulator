"""Screen capture using macOS Quartz (CoreGraphics)."""

import hashlib
import logging

import Quartz

logger = logging.getLogger(__name__)


def get_all_displays() -> list[int]:
    """Enumerate all active displays. Returns list of display IDs."""
    max_displays = 16
    (err, display_ids, count) = Quartz.CGGetActiveDisplayList(max_displays, None, None)
    if err != 0:
        logger.error("CGGetActiveDisplayList failed with error %d", err)
        return [Quartz.CGMainDisplayID()]
    displays = list(display_ids[:count])
    logger.debug("found %d displays: %s", len(displays), displays)
    return displays


def capture_display(display_id: int) -> object | None:
    """Capture a screenshot of the given display. Returns CGImage or None."""
    image = Quartz.CGDisplayCreateImage(display_id)
    if image is None:
        logger.warning("CGDisplayCreateImage returned None for display %d", display_id)
        return None
    logger.debug(
        "captured display %d: %dx%d",
        display_id,
        Quartz.CGImageGetWidth(image),
        Quartz.CGImageGetHeight(image),
    )
    return image


def hash_image(cg_image: object) -> str:
    """Compute SHA-256 hash of CGImage bitmap data for change detection."""
    data_provider = Quartz.CGImageGetDataProvider(cg_image)
    if data_provider is None:
        return ""
    raw_data = Quartz.CGDataProviderCopyData(data_provider)
    if raw_data is None:
        return ""
    return hashlib.sha256(bytes(raw_data)).hexdigest()
