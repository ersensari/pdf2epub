"""Image preprocessing: denoising, skew correction, contrast enhancement.

Improves scanned page quality before OCR and for better EPUB rendering.
"""

import io

import cv2
import numpy as np
from PIL import Image, ImageEnhance


def enhance_page_image(image_png: bytes, target_dpi: int = 300) -> bytes:
    """Enhance a scanned page: denoise, fix contrast, correct skew.

    Args:
        image_png: Raw PNG bytes from page render.
        target_dpi: Target DPI; used to estimate filter kernel sizes.

    Returns:
        Enhanced PNG bytes.
    """
    pil_image = Image.open(io.BytesIO(image_png))
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # Denoise: reduce scanning artifacts without blurring text.
    cv_image = cv2.fastNlMeansDenoisingColored(cv_image, h=10, templateWindowSize=7, searchWindowSize=21)

    # Convert to grayscale for skew detection + contrast.
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

    # Adaptive contrast: bring faded text closer to black, background closer to white.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Skew correction: detect and rotate if the page is tilted.
    skew_angle = _detect_skew(gray)
    if abs(skew_angle) > 0.5:
        h, w = gray.shape
        center = (w // 2, h // 2)
        rot_matrix = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        gray = cv2.warpAffine(gray, rot_matrix, (w, h), borderMode=cv2.BORDER_REFLECT)
        cv_image = cv2.warpAffine(cv_image, rot_matrix, (w, h), borderMode=cv2.BORDER_REFLECT)

    # Convert back to RGB and then PIL for PNG export.
    cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(cv_image)

    # Sharpen slightly to enhance text readability.
    enhancer = ImageEnhance.Sharpness(result_pil)
    result_pil = enhancer.enhance(1.3)

    # Export as PNG.
    output = io.BytesIO()
    result_pil.save(output, format="PNG")
    return output.getvalue()


def _detect_skew(gray_image: np.ndarray, max_angle: float = 10.0) -> float:
    """Estimate page skew angle in degrees.

    Uses Hough transform on edge-detected image. Returns angle in [-max_angle, max_angle].
    """
    edges = cv2.Canny(gray_image, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for line in lines[:20]:  # sample first 20 lines to avoid outliers
        rho, theta = line[0]
        angle = np.degrees(theta) - 90
        if abs(angle) <= max_angle:
            angles.append(angle)

    if not angles:
        return 0.0

    # Use median to reduce outliers.
    return float(np.median(angles))
