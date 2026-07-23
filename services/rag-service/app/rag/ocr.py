"""
OCR — RAG_SYSTEM.md §2.2: "an OCR fallback specifically for scanned legacy
documents (older DGMS circulars in particular are frequently only available
as scanned PDFs) ... OCR output carries its own `ocr_confidence` field, and
any chunk sourced from a below-threshold-confidence OCR pass is flagged in
its metadata."

Uses `easyocr` (a real, local neural OCR engine — no Tesseract system binary
required, which matters in this environment) rather than a system-dependent
CLI tool, so this path runs the same way in every deployment.
"""

from __future__ import annotations

import io

import numpy as np
import structlog
from PIL import Image

logger = structlog.get_logger(__name__)

LOW_CONFIDENCE_THRESHOLD = 0.5


class OcrEngine:
    """Lazily-initialized wrapper around one loaded easyocr.Reader -- loading
    the model is expensive enough that it must happen once, not per request."""

    def __init__(self) -> None:
        self._reader = None

    def _get_reader(self):
        if self._reader is None:
            import easyocr

            logger.info("ocr_model_loading")
            self._reader = easyocr.Reader(["en"], gpu=False)
            logger.info("ocr_model_loaded")
        return self._reader

    def warm_up(self) -> None:
        self._get_reader()

    def extract_text(self, image_bytes: bytes) -> tuple[str, float]:
        """Returns (extracted_text, mean_confidence). mean_confidence is the
        unweighted average of easyocr's per-detected-line confidence, which is
        exactly the `ocr_confidence` field RAG_SYSTEM.md §2.2/§6 specifies."""
        reader = self._get_reader()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        results = reader.readtext(np.array(image), detail=1)
        if not results:
            return "", 0.0
        lines = [text for _, text, _ in results]
        confidences = [float(conf) for _, _, conf in results]
        return "\n".join(lines), sum(confidences) / len(confidences)


ocr_engine = OcrEngine()
