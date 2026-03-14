"""OCR using macOS Vision framework (CoreML, on-device)."""

import logging

import Quartz
import Vision

logger = logging.getLogger(__name__)


def ocr_image(cg_image: object) -> str:
    """Run OCR on a CGImage. Returns recognized text."""
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cg_image, None
    )

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    success = handler.performRequests_error_([request], None)
    if not success[0]:
        error = success[1]
        logger.warning("OCR failed: %s", error)
        return ""

    results = request.results()
    if not results:
        logger.debug("OCR returned no text")
        return ""

    lines = []
    for observation in results:
        candidate = observation.topCandidates_(1)
        if candidate:
            lines.append(candidate[0].string())

    text = "\n".join(lines)
    logger.debug("OCR recognized %d lines, %d chars", len(lines), len(text))
    return text
