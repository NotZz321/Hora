#!/usr/bin/env python3
"""Read the 12-sign Thai *rasi-chakra* layout from a screenshot.

This is an image *extractor*, not an astrological position calculator.
The layout is the square/diagonal 12-cell wheel seen in the supplied example:
Aries is at the top, signs continue counterclockwise, and Thai digits ๐–๙
inside the cells denote planets. OCR is fallible: always review the result.

Install (recommended Thai OCR):
    pip install opencv-python-headless numpy paddleocr paddlepaddle
Optional baseline: pip install pytesseract; install Tesseract and Thai "tha" data.

Examples:
    python chart_image_reader.py --input-dir raw --output-dir results
    python chart_image_reader.py chart.png --output chart.json --debug debug.png
    python chart_image_reader.py chart.png --paddle-model-dir /path/to/th_PP-OCRv5_mobile_rec_infer
    python chart_image_reader.py chart.png --ocr-engine tesseract
    python chart_image_reader.py chart.png --aries-point 365 186
    python chart_image_reader.py chart.png --rotation-deg 15 --ascendant-sign พิจิก

The --aries-point coordinates mark the middle of the *outer* word เมษ.
Rotation is positive clockwise in the input image; either setting overrides
OCR-based orientation detection. If OCR cannot locate เมษ, the program assumes
an upright chart, marks that assumption, and requires manual review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

SIGNS = (
    "เมษ", "พฤษภ", "มิถุน", "กรกฎ", "สิงห์", "กันย์", "ตุลย์", "พิจิก",
    "ธนู", "มังกร", "กุมภ์", "มีน",
)
PLANETS = {
    "๐": "มฤตยู", "๑": "อาทิตย์", "๒": "จันทร์", "๓": "อังคาร",
    "๔": "พุธ", "๕": "พฤหัสบดี", "๖": "ศุกร์", "๗": "เสาร์",
    "๘": "ราหู", "๙": "เกตุ",
}
THAI_DIGITS = set(PLANETS)
ASCII_TO_THAI = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"})


@dataclass
class Circle:
    x: float
    y: float
    radius: float


def sign_index(dx: float, dy: float, radius: float, center_fraction: float = 0.18) -> int | None:
    """Classify a pixel in the *nonuniform*, 12-cell Thai diagram.

    Coordinates are relative to the circle center after uprighting the wheel.
    The 12 sectors are divided by horizontal/vertical lines and four diagonals;
    treating them as 12 uniform angular sectors would misassign some glyphs.
    """
    if radius <= 0:
        raise ValueError("radius must be positive")
    u, v = dx / radius, dy / radius  # v positive toward bottom of image
    a = center_fraction
    if abs(u) <= a and abs(v) <= a:
        return None  # Center label (e.g. 27°39′), NOT a planet.
    if abs(u) <= a:
        return 0 if v < -a else (6 if v > a else None)
    if abs(v) <= a:
        return 3 if u < -a else 9
    if u < -a and v < -a:
        return 1 if v < u else 2                 # NW: Taurus / Gemini
    if u < -a and v > a:
        return 4 if v < -u else 5                # SW: Leo / Virgo
    if u > a and v > a:
        return 7 if v > u else 8                 # SE: Scorpio / Sagittarius
    if u > a and v < -a:
        return 11 if -v > u else 10              # NE: Pisces / Aquarius
    return None


def clockwise_rotation_from_aries(x: float, y: float, circle: Circle) -> float:
    """0 means เมษ at 12 o'clock. Positive = input image rotated clockwise."""
    angle = math.degrees(math.atan2(y - circle.y, x - circle.x))
    return (angle + 90.0 + 180.0) % 360.0 - 180.0


def need_cv():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Install dependencies: pip install opencv-python-headless numpy") from exc
    return cv2, np


def need_ocr():
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("Install OCR support: pip install pytesseract") from exc
    try:
        langs = pytesseract.get_languages(config="")
    except Exception as exc:
        raise RuntimeError("Tesseract OCR executable was not found on PATH") from exc
    if "tha" not in langs:
        raise RuntimeError(
            "Tesseract Thai language data is missing. Install 'tesseract-ocr-tha' "
            "(Ubuntu/Debian), then check: tesseract --list-langs"
        )
    return pytesseract


def read_image(path: Path):
    cv2, np = need_cv()
    raw = np.fromfile(str(path), dtype=np.uint8)
    if not len(raw):
        raise ValueError(f"Empty or missing image: {path}")
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unable to decode image: {path}")
    return image


def detect_outer_circle(image) -> Circle:
    cv2, np = need_cv()
    h, w = image.shape[:2]
    scale = min(h, w)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.2)
    candidates = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=1.0, minDist=0.30 * scale,
        param1=125, param2=37,
        minRadius=max(25, round(0.20 * scale)),
        maxRadius=round(0.48 * scale),
    )
    if candidates is None:
        raise ValueError("No circular zodiac chart found. Crop closer to the wheel.")

    # Favor a real near-complete circumference, not the inner ring or text.
    edges = cv2.Canny(blurred, 70, 160)
    best_score, best = -1.0, None
    angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    for x, y, r in candidates[0]:
        if x - r < -3 or y - r < -3 or x + r >= w + 3 or y + r >= h + 3:
            continue
        votes = []
        for offset in (-2.0, 0.0, 2.0):
            xs = np.round(x + (r + offset) * np.cos(angles)).astype(int)
            ys = np.round(y + (r + offset) * np.sin(angles)).astype(int)
            valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
            edge_votes = np.zeros_like(valid, dtype=bool)
            edge_votes[valid] = edges[ys[valid], xs[valid]] > 0
            votes.append(edge_votes)
        coverage = float(np.stack(votes).any(axis=0).mean())
        score = coverage + 0.05 * float(r / scale)
        if coverage > 0.23 and score > best_score:
            best_score = score
            best = Circle(float(x), float(y), float(r))
    if best is None:
        raise ValueError("Circles were detected, but none had a reliable outer border")
    return best


def image_to_words(image, lang="tha", psm=11):
    ocr = need_ocr()
    cv2, np = need_cv()
    from pytesseract import Output
    if image.ndim == 3:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        rgb = image
    table = ocr.image_to_data(
        rgb, lang=lang, config=f"--oem 1 --psm {psm} --dpi 300",
        output_type=Output.DICT,
    )
    words = []
    for i, raw in enumerate(table["text"]):
        word = str(raw).strip()
        if not word:
            continue
        try:
            confidence = float(table["conf"][i])
        except ValueError:
            confidence = -1.0
        words.append({
            "text": word, "confidence": round(confidence, 2),
            "x": int(table["left"][i]), "y": int(table["top"][i]),
            "w": int(table["width"][i]), "h": int(table["height"][i]),
        })
    return words


def detect_aries_anchor(image, circle: Circle):
    """Find the outer word เมษ when horizontal OCR works; return (x,y) or None.

    No silent guessing from a colored dot or chart 'north': there is no globally
    fixed photographic rotation. A caller may provide the word's point instead.
    """
    cv2, np = need_cv()
    h, w = image.shape[:2]
    min_x = max(0, round(circle.x - 1.20 * circle.radius))
    min_y = max(0, round(circle.y - 1.20 * circle.radius))
    max_x = min(w, round(circle.x + 1.20 * circle.radius))
    max_y = min(h, round(circle.y + 1.20 * circle.radius))
    patch = image[min_y:max_y, min_x:max_x]
    # Try a normal and 2x version; OCR confidence varies by screenshot scale.
    for factor in (1, 2):
        candidate = cv2.resize(patch, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        for word in image_to_words(candidate, psm=11):
            text = re.sub(r"[^ก-๙]", "", word["text"])
            similarity = SequenceMatcher(None, text, "เมษ").ratio()
            if similarity < 0.79 or word["confidence"] < 12:
                continue
            x = min_x + (word["x"] + word["w"] / 2) / factor
            y = min_y + (word["y"] + word["h"] / 2) / factor
            distance = math.hypot(x - circle.x, y - circle.y)
            if 0.83 * circle.radius <= distance <= 1.21 * circle.radius:
                return (float(x), float(y))
    return None


def rotate_upright(image, circle: Circle, clockwise_degrees: float):
    cv2, _ = need_cv()
    # OpenCV's positive rotation is CCW; it undoes a positive CW input tilt.
    matrix = cv2.getRotationMatrix2D((circle.x, circle.y), clockwise_degrees, 1.0)
    h, w = image.shape[:2]
    upright = cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255),
    )
    return upright, matrix


def erase_chart_lines(image, circle: Circle):
    cv2, np = need_cv()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    # Structural lines are much longer than single Thai glyph strokes.
    k = max(28, round(circle.radius * 0.23))
    line_mask = np.zeros_like(ink)
    for angle in (0, 45, 90, 135):
        kernel = np.zeros((k, k), np.uint8)
        if angle == 0:
            kernel[k // 2, :] = 1
        elif angle == 90:
            kernel[:, k // 2] = 1
        elif angle == 45:
            np.fill_diagonal(np.fliplr(kernel), 1)
        else:
            np.fill_diagonal(kernel, 1)
        detected = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
        line_mask = cv2.bitwise_or(line_mask, detected)
    cleaned = image.copy()
    cleaned[cv2.dilate(line_mask, np.ones((2, 2), np.uint8)) > 0] = (255, 255, 255)
    return cleaned


def cell_masks(circle: Circle, image_shape, min_radius=0.23, max_radius=0.80):
    """Pixel masks for the 12 inner *sign* cells, before OCR."""
    _, np = need_cv()
    h, w = image_shape[:2]
    yy, xx = np.ogrid[:h, :w]
    u = (xx - circle.x) / circle.radius
    v = (yy - circle.y) / circle.radius
    a = 0.18
    rad2 = u * u + v * v
    # The *outer* blue sign names sit farther out than the planets. Avoid
    # including their letter fragments, which OCR may mistake for Thai digits.
    ring = (rad2 >= min_radius**2) & (rad2 <= max_radius**2)
    masks = [None] * 12
    masks[0] = (abs(u) <= a) & (v < -a)
    masks[6] = (abs(u) <= a) & (v > a)
    masks[3] = (u < -a) & (abs(v) <= a)
    masks[9] = (u > a) & (abs(v) <= a)
    masks[1] = (u < -a) & (v < -a) & (v < u)
    masks[2] = (u < -a) & (v < -a) & (v >= u)
    masks[4] = (u < -a) & (v > a) & (v < -u)
    masks[5] = (u < -a) & (v > a) & (v >= -u)
    masks[7] = (u > a) & (v > a) & (v > u)
    masks[8] = (u > a) & (v > a) & (v <= u)
    masks[11] = (u > a) & (v < -a) & (-v > u)
    masks[10] = (u > a) & (v < -a) & (-v <= u)
    return [(m & ring).astype(np.uint8) * 255 for m in masks]


def ocr_per_sign(image, masks, color_reference=None):
    cv2, np = need_cv()
    results = []
    if color_reference is None:
        color_reference = image
    for idx, mask in enumerate(masks):
        points = cv2.findNonZero(mask)
        if points is None:
            results.append({"sign_index": idx, "words": [], "planets": [], "ascendant": False})
            continue
        x, y, w, h = cv2.boundingRect(points)
        img = image[y:y + h, x:x + w].copy()
        img[mask[y:y + h, x:x + w] == 0] = (255, 255, 255)
        factor = 3
        img = cv2.resize(img, (w * factor, h * factor), interpolation=cv2.INTER_CUBIC)
        words = image_to_words(img, psm=11)
        planets = []
        ascendant = False
        for word in words:
            if word["confidence"] < 18:
                continue
            raw = word["text"]
            bx, by = round(x + word["x"] / factor), round(y + word["y"] / factor)
            bw, bh = max(1, round(word["w"] / factor)), max(1, round(word["h"] / factor))
            color_patch = color_reference[by:by + bh, bx:bx + bw]
            if color_patch.size:
                b, g, r = [color_patch[:, :, k].astype(float) for k in range(3)]
                red_pixels = (r > 65) & (r > g * 1.35) & (r > b * 1.35)
                colored = (color_patch.min(axis=2) < 185)
                fraction = float(red_pixels.sum()) / max(1, int(colored.sum()))
                ink_color = "red" if fraction >= .64 else ("mixed" if fraction >= .16 else "black")
            else:
                ink_color = "unknown"
            # A string like '๑๖' represents TWO planets, not number 16.
            for digit in raw:
                if digit in THAI_DIGITS:
                    planets.append({
                        "symbol": digit,
                        "name": PLANETS[digit],
                        "confidence": word["confidence"],
                        "ink_color": ink_color,
                        "source": "ocr",
                        "ocr_text": raw,
                        "bbox_input_px": [
                            bx, by, bw, bh,
                        ],
                    })
            if "ลั" in raw or re.search(r"(?<![ก-ฮ])ล(?![ก-ฮ])", raw):
                ascendant = True
        results.append({"sign_index": idx, "words": words, "planets": planets, "ascendant": ascendant})
    return results


def load_paddle_recognizer(model_dir=None, device="cpu"):
    """Load the 7.5 MB Thai PP-OCRv5 recognition model (no text detector)."""
    try:
        from paddleocr import TextRecognition
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is missing. Install: pip install paddleocr paddlepaddle"
        ) from exc
    options = {"model_name": "th_PP-OCRv5_mobile_rec", "device": device}
    if model_dir:
        target = Path(model_dir).expanduser()
        if not (target / "inference.json").is_file():
            raise ValueError("Paddle model directory must contain inference.json")
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        options["model_dir"] = str(target)
    try:
        return TextRecognition(**options)
    except Exception as exc:
        raise RuntimeError(
            "Unable to load Thai PP-OCRv5 Mobile. Supply --paddle-model-dir "
            "with downloaded model files if automatic download is blocked."
        ) from exc


def paddle_read_line(model, bgr_image):
    """Return single-line recognition text/score for a tightly cropped image."""
    cv2, _ = need_cv()
    h, w = bgr_image.shape[:2]
    if h < 2 or w < 2:
        return "", 0.0
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    factor = max(1, min(5, round(150 / max(h, w))))
    if factor > 1:
        rgb = cv2.resize(rgb, (w * factor, h * factor), interpolation=cv2.INTER_CUBIC)
    results = model.predict(input=rgb, batch_size=1)
    for item in results:
        result = item.json["res"]
        return str(result.get("rec_text", "")), float(result.get("rec_score", 0.0))
    return "", 0.0


def find_planet_text_crops(cleaned, upright, masks):
    """Locate short Thai-digit clusters with geometry and connected components.

    Filtering blue zodiac labels and long chart lines first is important:
    the recognition model should receive only a *short text line*, not a full
    12-sign diagram or a large crop of mostly white space.
    """
    cv2, np = need_cv()
    b, g, r = [cleaned[:, :, k].astype(np.int16) for k in range(3)]
    black = (b < 150) & (g < 150) & (r < 150)
    red = (r > 75) & (r > 1.4 * g) & (r > 1.4 * b)
    ink = black | red
    crops = []
    for idx, mask in enumerate(masks):
        scoped_ink = (ink & (mask > 0)).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(scoped_ink)
        components = [
            stats[i] for i in range(1, count)
            if stats[i, cv2.CC_STAT_AREA] >= 5
            and stats[i, cv2.CC_STAT_WIDTH] >= 2
            and stats[i, cv2.CC_STAT_HEIGHT] >= 3
        ]
        if not components:
            continue
        pad = 10
        x0 = max(0, int(min(s[0] for s in components)) - pad)
        y0 = max(0, int(min(s[1] for s in components)) - pad)
        x1 = min(cleaned.shape[1], int(max(s[0] + s[2] for s in components)) + pad)
        y1 = min(cleaned.shape[0], int(max(s[1] + s[3] for s in components)) + pad)
        roi = upright[y0:y1, x0:x1]
        if roi.size:
            # Preserve the original pixel colors: red/black may be separate
            # astrological layers, depending on the source app.
            crops.append({"index": idx, "bbox": [x0, y0, x1 - x0, y1 - y0], "image": roi})
    return crops


def ocr_per_sign_paddle(upright, circle, model):
    cv2, np = need_cv()
    cleaned = erase_chart_lines(upright, circle)
    masks = cell_masks(circle, upright.shape)
    rois = find_planet_text_crops(cleaned, upright, masks)
    records = [
        {"sign_index": i, "words": [], "planets": [], "ascendant": False}
        for i in range(12)
    ]
    for roi in rois:
        idx, bbox = roi["index"], roi["bbox"]
        raw, score = paddle_read_line(model, roi["image"])
        # The Thai model sometimes returns an ASCII glyph for a Thai numeral;
        # convert 0-9 deterministically, keeping original OCR evidence.
        normalized = raw.translate(ASCII_TO_THAI)
        rgb = roi["image"].astype(float)
        b, g, r = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        red_pixels = (r > 75) & (r > g * 1.4) & (r > b * 1.4)
        dark_pixels = rgb.min(axis=2) < 180
        red_ratio = float(red_pixels.sum()) / max(1, int(dark_pixels.sum()))
        color = "red" if red_ratio >= .64 else ("mixed" if red_ratio >= .16 else "black")
        records[idx]["words"].append({
            "text": raw, "normalized": normalized,
            "confidence": round(score * 100, 2),
            "bbox_input_px": bbox,
        })
        for char in normalized:
            if char in THAI_DIGITS and score >= .20:
                records[idx]["planets"].append({
                    "symbol": char, "name": PLANETS[char],
                    "confidence": round(score * 100, 2),
                    "ink_color": color,
                    "source": "paddle_th_mobile_v5",
                    "ocr_text": raw,
                    "bbox_input_px": bbox,
                    "ascii_digit_normalized": char not in raw,
                })
        if "ลั" in raw or re.search(r"(?<![ก-ฮ])ล(?![ก-ฮ])", raw):
            records[idx]["ascendant"] = True
    return records


def apply_manual_corrections(records, corrections):
    """Replace uncertain sign readings with reviewed symbols, preserving raw OCR.

    Example corrections JSON:
      {"ascendant_sign": "พิจิก", "planets": {"เมษ": [
        {"symbol": "๘", "ink_color": "black"}]}}
    For a sign with no planets use an empty list; unlisted signs keep OCR output.
    """
    if not isinstance(corrections, dict):
        raise ValueError("Corrections file must contain a JSON object")
    planet_changes = corrections.get("planets", {})
    if not isinstance(planet_changes, dict):
        raise ValueError("Corrections 'planets' must be a sign-name to list mapping")
    for sign_name, replacement in planet_changes.items():
        idx = convert_sign(sign_name)
        if not isinstance(replacement, list):
            raise ValueError(f"Corrections for {sign_name} must be a list")
        planets = []
        for entry in replacement:
            if isinstance(entry, str):
                entry = {"symbol": entry}
            if not isinstance(entry, dict) or entry.get("symbol") not in PLANETS:
                raise ValueError(f"Invalid planet symbol for {sign_name}: {entry!r}")
            color = entry.get("ink_color", "unknown")
            if color not in ("red", "black", "mixed", "unknown"):
                raise ValueError("ink_color must be red, black, mixed, or unknown")
            planets.append({
                "symbol": entry["symbol"], "name": PLANETS[entry["symbol"]],
                "confidence": 100.0, "ink_color": color, "source": "manual_review",
                "ocr_text": None, "bbox_input_px": None,
            })
        records[idx]["planets"] = planets


def detect_red_outer_ascendant(image, circle: Circle, paddle_model=None):
    """Attempt to read a red ล / ลั marker outside the ring, if the style uses it."""
    cv2, np = need_cv()
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 85, 55), (11, 255, 255)),
        cv2.inRange(hsv, (170, 85, 55), (179, 255, 255)),
    )
    n, _, stats, centroids = cv2.connectedComponentsWithStats(red)
    for i in range(1, n):
        x, y, w, h, area = map(int, stats[i])
        px, py = map(float, centroids[i])
        radial = math.hypot(px - circle.x, py - circle.y) / circle.radius
        if not (0.88 <= radial <= 1.35 and 8 <= area <= 700 and 6 <= w <= 65 and 6 <= h <= 65):
            continue
        margin = 9
        x0, y0 = max(0, x - margin), max(0, y - margin)
        x1, y1 = min(image.shape[1], x + w + margin), min(image.shape[0], y + h + margin)
        patch = image[y0:y1, x0:x1]
        if paddle_model is not None:
            symbol, confidence = paddle_read_line(paddle_model, patch)
            if confidence < .25:
                continue
        else:
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            expanded = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
            ocr = need_ocr()
            symbol = ocr.image_to_string(expanded, lang="tha", config="--oem 1 --psm 10").strip()
        if "ล" in symbol:
            idx = sign_index(px - circle.x, py - circle.y, circle.radius)
            if idx is not None:
                return (idx, [round(px), round(py)], symbol)
    return None


def convert_sign(value: str) -> int:
    fixed = "ตุลย์" if value.strip() == "ตุล" else value.strip()
    for i, sign in enumerate(SIGNS):
        if fixed == sign or value == str(i):
            return i
    raise ValueError(f"Unknown zodiac sign '{value}' (use Thai name or index 0..11)")


def overlay(image, circle: Circle, results, rotation_info: str):
    cv2, _ = need_cv()
    marked = image.copy()
    center = (round(circle.x), round(circle.y))
    cv2.circle(marked, center, round(circle.radius), (0, 155, 255), 2)
    cv2.circle(marked, center, 3, (0, 0, 255), -1)
    for record in results:
        idx = record["sign_index"]
        # Display positions are cell centers, not a fabricated 30-degree ray.
        mapping = {
            0:(0,-.55), 1:(-.45,-.58), 2:(-.58,-.34), 3:(-.57,0),
            4:(-.58,.34), 5:(-.45,.58), 6:(0,.57), 7:(.45,.58),
            8:(.58,.34), 9:(.57,0), 10:(.58,-.34), 11:(.45,-.58),
        }
        ux, vy = mapping[idx]
        pos = (round(circle.x + ux*circle.radius), round(circle.y + vy*circle.radius))
        cv2.putText(marked, f"{idx}:{len(record['planets'])}", pos,
                    cv2.FONT_HERSHEY_SIMPLEX, .36, (190, 80, 20), 1, cv2.LINE_AA)
    cv2.putText(marked, rotation_info[:70], (12, image.shape[0]-12),
                cv2.FONT_HERSHEY_SIMPLEX, .4, (5, 90, 5), 1, cv2.LINE_AA)
    return marked


def process(image, rotation_override=None, aries_point=None, ascendant_override=None,
            corrections=None, ocr_engine="tesseract", paddle_model_dir=None,
            paddle_device="cpu", paddle_model=None):
    if ocr_engine not in ("tesseract", "paddle"):
        raise ValueError("ocr_engine must be paddle or tesseract")
    circle = detect_outer_circle(image)
    if aries_point is not None:
        rotation = clockwise_rotation_from_aries(*aries_point, circle)
        orientation_source = "manual_aries_point"
    elif rotation_override is not None:
        rotation = float(rotation_override)
        orientation_source = "manual_rotation_degrees_clockwise"
    else:
        try:
            found = detect_aries_anchor(image, circle)
        except RuntimeError:
            if ocr_engine == "tesseract":
                raise
            # Paddle is a text-line recognizer and does not independently
            # locate a word around a rotated wheel. Use --aries-point for an
            # unambiguous orientation if Tesseract is not installed.
            found = None
        if found is None:
            rotation, orientation_source = 0.0, "assumed_upright_unverified"
        else:
            rotation = clockwise_rotation_from_aries(*found, circle)
            orientation_source = "ocr_aries_anchor"

    upright, _ = rotate_upright(image, circle, rotation)
    if ocr_engine == "paddle":
        if paddle_model is None:
            paddle_model = load_paddle_recognizer(paddle_model_dir, paddle_device)
        records = ocr_per_sign_paddle(upright, circle, paddle_model)
    else:
        cleaned = erase_chart_lines(upright, circle)
        records = ocr_per_sign(cleaned, cell_masks(circle, upright.shape), upright)
    if corrections:
        apply_manual_corrections(records, corrections)
    lagna_candidates = [row["sign_index"] for row in records if row["ascendant"]]
    red_lagna = detect_red_outer_ascendant(upright, circle, paddle_model)
    if red_lagna is not None:
        lagna_candidates.append(red_lagna[0])
    if ascendant_override is None and corrections:
        ascendant_override = corrections.get("ascendant_sign")
    if ascendant_override is not None:
        ascendant = convert_sign(ascendant_override)
        ascendant_source = "manual_override"
    elif len(set(lagna_candidates)) == 1:
        ascendant = lagna_candidates[0]
        ascendant_source = "ocr_symbol"
    else:
        ascendant = None
        ascendant_source = "not_found_or_ambiguous"

    warnings = []
    if orientation_source == "assumed_upright_unverified":
        warnings.append("Couldn't verify เมษ anchor: image assumed upright; check rotation")
    if ascendant is None:
        warnings.append("Ascendant (ล/ลั) missing or ambiguous; house indices not computed")

    all_planets = [p for row in records for p in row["planets"]]
    found_symbols = {p["symbol"] for p in all_planets}
    missing = sorted(THAI_DIGITS - found_symbols)
    if missing:
        warnings.append("OCR missed some planet symbols: " + " ".join(missing))
    if ocr_engine == "paddle":
        ambiguous = []
        reviewed_indices = {
            convert_sign(sign_name)
            for sign_name in (corrections or {}).get("planets", {})
        }
        for row in records:
            if row["sign_index"] in reviewed_indices:
                continue
            for word in row["words"]:
                remainder = "".join(
                    c for c in word["normalized"]
                    if c not in THAI_DIGITS and not c.isspace() and c not in "ลั"
                )
                if remainder:
                    ambiguous.append(f"{SIGNS[row['sign_index']]}={word['text']}")
        if ambiguous:
            warnings.append("Unrecognized glyphs alongside planets: " + ", ".join(ambiguous))
    # A screenshot can overlay a moving/transit chart, so red and black copies
    # of a planet are NOT automatically OCR duplicates.
    duplicate = [digit for digit in THAI_DIGITS if
                 sum(p["symbol"] == digit and p["ink_color"] == "black"
                     for p in all_planets) > 1]
    if duplicate:
        warnings.append("Possibly duplicated planet readings: " + " ".join(sorted(duplicate)))

    zodiac = []
    for row in records:
        idx = row["sign_index"]
        zodiac.append({
            "sign_index": idx, "sign": SIGNS[idx],
            "house": ((idx - ascendant) % 12 + 1) if ascendant is not None else None,
            "planets": row["planets"],
            "is_ascendant": idx == ascendant if ascendant is not None else False,
            "ocr_raw_words": [x["text"] for x in row["words"]],
        })

    response = {
        "format": "thai_rasi_chakra_12_box",
        "ocr_engine": ocr_engine,
        "chart_geometry": {"circle": asdict(circle), "rotation_clockwise_deg": round(rotation, 2),
                           "orientation_source": orientation_source},
        "ascendant_sign": SIGNS[ascendant] if ascendant is not None else None,
        "ascendant_source": ascendant_source,
        "zodiac": zodiac,
        "planets_by_sign": {
            name: [SIGNS[r["sign_index"]] for r in records if any(p["name"] == name for p in r["planets"])]
            for name in PLANETS.values()
        },
        "warnings": warnings,
        "needs_review": bool(warnings),
        "note": "Ink color is recorded but its natal/transit meaning depends on the source app. "
                "A 12-sign chart alone does not give exact planet degrees, MC, or house cusps.",
    }
    return response, upright, records, circle


def self_test():
    circle = Circle(365, 382, 207)
    examples = {
        "เมษ": (0, -110), "พฤษภ": (-90, -120), "มิถุน": (-120, -70),
        "กรกฎ": (-120, 0), "สิงห์": (-120, 70), "กันย์": (-90, 120),
        "ตุลย์": (0, 120), "พิจิก": (90, 120), "ธนู": (120, 70),
        "มังกร": (120, 0), "กุมภ์": (120, -70), "มีน": (90, -120),
    }
    for expected_idx, (name, (dx, dy)) in enumerate(examples.items()):
        actual = sign_index(dx, dy, circle.radius)
        assert actual == expected_idx, (name, actual, expected_idx)
    assert sign_index(0, 0, 207) is None
    assert clockwise_rotation_from_aries(365, 175, circle) == 0
    assert round(clockwise_rotation_from_aries(465, 209, circle)) == 30
    assert convert_sign("ตุล") == 6
    print("Self-test passed: geometry, orientation and zodiac names")


CHART_CSV_COLUMNS = [
    "chart_id", "run_id", "source_image", "source_sha256", "status", "review_status",
    "ocr_needs_review", "ocr_engine", "ascendant_sign", "ascendant_source",
    "orientation_source", "rotation_clockwise_deg", "circle_center_x",
    "circle_center_y", "circle_radius", "recognized_planets", "unique_planet_symbols",
    "warnings", "error", "json_file", "debug_file",
]
PLANET_CSV_COLUMNS = [
    "chart_id", "run_id", "source_image", "planet_symbol", "planet_number",
    "planet_name", "sign_index_0based", "sign_number_1based", "sign_name",
    "house_number_1based", "ink_color", "confidence", "ocr_text", "source",
    "bbox_input_px", "review_status",
]


def find_raw_images(folder: Path) -> list[Path]:
    """Read only the images immediately inside raw/; sort X2 before X10."""
    if not folder.is_dir():
        raise ValueError(f"Input folder does not exist: {folder}")

    def natural_key(path: Path):
        parts = re.split(r"(\d+)", path.name.casefold())
        return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)

    images = [p for p in folder.iterdir()
              if p.is_file() and p.suffix.casefold() in IMAGE_SUFFIXES]
    return sorted(images, key=natural_key)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_debug(path: Path, upright, circle: Circle, records, result):
    cv2, _ = need_cv()
    marked = overlay(upright, circle, records,
                     result["chart_geometry"]["orientation_source"])
    success, data = cv2.imencode(path.suffix or ".png", marked)
    if not success:
        raise ValueError(f"Could not encode debug image: {path}")
    data.tofile(str(path))  # Supports Thai and other Unicode paths on Windows.


def run_raw_batch(folder: Path, output_dir: Path, args) -> Path:
    """Process every image once; keep CSV, raw OCR and debug evidence per run.

    All OCR-derived data is explicitly marked UNVERIFIED, even when its score
    is high. Do not feed these rows into career prediction before review.
    """
    images = find_raw_images(folder)
    if not images:
        raise ValueError(f"No images in {folder}; supported: {', '.join(sorted(IMAGE_SUFFIXES))}")
    if len(images) > 1 and any((args.aries_point is not None,
                               args.ascendant_sign is not None,
                               args.corrections is not None)):
        raise ValueError(
            "--aries-point, --ascendant-sign and --corrections are image-specific; "
            "use them with a single-image command, not a multi-image batch"
        )

    # Prepare the model before creating a run directory. If it is unavailable,
    # exit without leaving a misleading empty output run.
    paddle_model = None
    if args.ocr_engine == "paddle":
        paddle_model = load_paddle_recognizer(args.paddle_model_dir, args.paddle_device)

    # New output directory every time: never overwrite previous CSV results.
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    destination = output_dir / run_id
    destination.mkdir(parents=True, exist_ok=False)
    debug_dir = destination / "debug"
    json_dir = destination / "json"
    debug_dir.mkdir()
    json_dir.mkdir()

    corrections = (json.loads(args.corrections.read_text(encoding="utf-8"))
                   if args.corrections else None)
    failed = 0
    flagged = 0
    with (destination / "charts.csv").open("w", newline="", encoding="utf-8-sig") as chart_file, \
         (destination / "planets.csv").open("w", newline="", encoding="utf-8-sig") as planet_file:
        chart_writer = csv.DictWriter(chart_file, fieldnames=CHART_CSV_COLUMNS)
        planet_writer = csv.DictWriter(planet_file, fieldnames=PLANET_CSV_COLUMNS)
        chart_writer.writeheader()
        planet_writer.writeheader()

        for n, path in enumerate(images, start=1):
            chart_id = f"{run_id}_{n:04d}"
            base = f"{n:04d}_{path.stem}"
            # The sequence prefix keeps artifacts distinct if stems repeat.
            json_path = json_dir / f"{base}.json"
            debug_path = debug_dir / f"{base}.png"
            chart_row = {
                "chart_id": chart_id, "run_id": run_id,
                "source_image": path.name, "source_sha256": "",
                "status": "error", "review_status": "not_processed",
                "ocr_needs_review": True, "ocr_engine": args.ocr_engine,
            }
            print(f"[{n}/{len(images)}] {path.name}", flush=True)
            try:
                chart_row["source_sha256"] = file_sha256(path)
                image = read_image(path)
                result, upright, records, circle = process(
                    image, rotation_override=args.rotation_deg,
                    aries_point=args.aries_point,
                    ascendant_override=args.ascendant_sign,
                    corrections=corrections, ocr_engine=args.ocr_engine,
                    paddle_model_dir=args.paddle_model_dir,
                    paddle_device=args.paddle_device, paddle_model=paddle_model,
                )
                json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
                save_debug(debug_path, upright, circle, records, result)

                all_symbols = [p["symbol"] for cell in result["zodiac"]
                               for p in cell["planets"]]
                geometry = result["chart_geometry"]
                chart_row.update({
                    "status": "ocr_complete", "review_status": "unverified",
                    "ocr_needs_review": result["needs_review"],
                    "ascendant_sign": result["ascendant_sign"] or "",
                    "ascendant_source": result["ascendant_source"],
                    "orientation_source": geometry["orientation_source"],
                    "rotation_clockwise_deg": geometry["rotation_clockwise_deg"],
                    "circle_center_x": geometry["circle"]["x"],
                    "circle_center_y": geometry["circle"]["y"],
                    "circle_radius": geometry["circle"]["radius"],
                    "recognized_planets": len(all_symbols),
                    "unique_planet_symbols": len(set(all_symbols)),
                    "warnings": " | ".join(result["warnings"]),
                    "json_file": json_path.relative_to(destination).as_posix(),
                    "debug_file": debug_path.relative_to(destination).as_posix(),
                })
                for cell in result["zodiac"]:
                    for planet in cell["planets"]:
                        planet_writer.writerow({
                            "chart_id": chart_id, "run_id": run_id,
                            "source_image": path.name,
                            "planet_symbol": planet["symbol"],
                            "planet_number": int(planet["symbol"]),
                            "planet_name": planet["name"],
                            "sign_index_0based": cell["sign_index"],
                            "sign_number_1based": cell["sign_index"] + 1,
                            "sign_name": cell["sign"], "house_number_1based": cell["house"] or "",
                            "ink_color": planet["ink_color"],
                            "confidence": planet["confidence"],
                            "ocr_text": planet.get("ocr_text") or "",
                            "source": planet["source"],
                            "bbox_input_px": json.dumps(planet.get("bbox_input_px"), ensure_ascii=False),
                            "review_status": "unverified",
                        })
                if result["needs_review"]:
                    flagged += 1
                print(f"  OK: {len(all_symbols)} OCR planets; "
                      f"review={'YES' if result['needs_review'] else 'recommended'}")
            except Exception as exc:
                failed += 1
                chart_row["error"] = f"{type(exc).__name__}: {exc}"
                print(f"  ERROR: {chart_row['error']}", file=sys.stderr)
            finally:
                chart_writer.writerow(chart_row)
                chart_file.flush()
                planet_file.flush()

    print(f"CSV: {destination / 'charts.csv'}")
    print(f"CSV: {destination / 'planets.csv'}")
    print(f"Processed {len(images)} images: {failed} errors, {flagged} flagged by OCR. "
          "ALL successful results remain unverified until manually reviewed.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", nargs="?", type=Path,
                        help="Single PNG/JPG image; omit to batch-process raw/")
    parser.add_argument("--input-dir", type=Path, default=Path("raw"),
                        help="Folder of images in batch mode (default: raw)")
    parser.add_argument("--output-dir", type=Path, default=Path("results"),
                        help="Where to create a new batch run with CSVs (default: results)")
    parser.add_argument("--output", type=Path,
                        help="JSON output for single-image mode only")
    parser.add_argument("--debug", type=Path, help="Optional annotated PNG preview")
    parser.add_argument("--ocr-engine", choices=("paddle", "tesseract"), default="paddle",
                        help="Thai PaddleOCR Mobile (default) or Tesseract baseline")
    parser.add_argument("--paddle-model-dir", type=Path,
                        help="Folder containing official th_PP-OCRv5_mobile_rec inference model")
    parser.add_argument("--paddle-device", default="cpu", help="cpu (default) or gpu")
    parser.add_argument("--aries-point", nargs=2, type=float, metavar=("X", "Y"),
                        help="Center of the outer word เมษ in ORIGINAL image pixels")
    parser.add_argument("--rotation-deg", type=float,
                        help="Manual INPUT rotation in degrees, positive clockwise")
    parser.add_argument("--ascendant-sign", type=str,
                        help="Manual ลัคนา zodiac name (or 0..11) if OCR fails")
    parser.add_argument("--corrections", type=Path,
                        help="Optional JSON with reviewed planet symbols per sign and ascendant_sign")
    parser.add_argument("--self-test", action="store_true", help="Run geometry unit tests (no OCR required)")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.aries_point is not None and args.rotation_deg is not None:
        parser.error("Choose only one of --aries-point and --rotation-deg")

    if args.image is None or args.image.is_dir():
        if args.output is not None or args.debug is not None:
            parser.error("--output/--debug are for a single image; "
                         "batch mode uses --output-dir and saves both automatically")
        source_dir = args.image if args.image is not None else args.input_dir
        try:
            run_raw_batch(source_dir, args.output_dir, args)
        except (ValueError, RuntimeError, OSError) as exc:
            parser.exit(2, f"Batch error: {exc}\n")
        return

    image = read_image(args.image)
    corrections = json.loads(args.corrections.read_text(encoding="utf-8")) if args.corrections else None
    result, upright, records, circle = process(
        image, rotation_override=args.rotation_deg,
        aries_point=args.aries_point, ascendant_override=args.ascendant_sign,
        corrections=corrections, ocr_engine=args.ocr_engine,
        paddle_model_dir=args.paddle_model_dir, paddle_device=args.paddle_device,
    )
    json_output = args.output or Path("chart_result.json")
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.debug:
        args.debug.parent.mkdir(parents=True, exist_ok=True)
        save_debug(args.debug, upright, circle, records, result)
    print(f"Saved: {json_output}")
    print(f"Circle: {circle} | Rotation: {result['chart_geometry']['rotation_clockwise_deg']}°")
    print(f"Ascendant: {result['ascendant_sign'] or 'unresolved'}")
    for sign in result["zodiac"]:
        names = ", ".join(p["name"] for p in sign["planets"]) or "—"
        print(f"  {sign['sign']:<8} : {names}")
    for warning in result["warnings"]:
        print("REVIEW:", warning, file=sys.stderr)


if __name__ == "__main__":
    main()
