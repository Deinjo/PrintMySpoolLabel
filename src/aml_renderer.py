from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import qrcode
from PIL import Image, ImageDraw, ImageFont


TARGET_SIZE = (320, 96)
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
MATERIAL_PREFIXES = ("PLA", "PETG", "ABS", "ASA", "TPU", "PC", "PA", "PVA", "HIPS")
TECHNICAL_MAX_VALUES = ("200-210°C", "50-100°C", "1.00", "99mm³/s")
ProgressCallback = Callable[[str], None]


class AmlError(ValueError):
    pass


@dataclass(frozen=True)
class AmlLabelData:
    manufacturer: str
    material: str
    color: str
    color_hex: str
    nozzle: str
    bed: str
    flow_ratio: str
    max_volumetric_speed: str
    qr_url: str
    logo: Image.Image | None
    qr_image: Image.Image | None = None


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, bold: bool = False):
    size = start_size
    while size > 7:
        font = _font(size, bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 1
    return _font(7, bold)


def _parse_measurements(texts: list[str]) -> tuple[str, str, str, str]:
    for text in texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 4:
            continue
        if "°" in lines[0] or "C" in lines[0] or "°" in lines[1] or "C" in lines[1]:
            return lines[0], lines[1], lines[2], lines[3]
    return "", "", "", ""


def _crop_raster_logo(image: Image.Image) -> Image.Image:
    """Keep the original manufacturer artwork instead of recreating it as text."""
    header = image.convert("RGB").crop((0, 0, image.width, min(130, image.height)))
    pixels = header.load()
    points = [
        (x, y)
        for y in range(header.height)
        for x in range(header.width)
        if min(pixels[x, y]) < 245
    ]
    if not points:
        return header.convert("RGBA")
    left = max(0, min(x for x, _y in points) - 4)
    top = max(0, min(y for _x, y in points) - 4)
    right = min(header.width, max(x for x, _y in points) + 5)
    bottom = min(header.height, max(y for _x, y in points) + 5)
    # Some exports contain a one-pixel separator below the logo. It is not
    # part of the manufacturer artwork and becomes visible after scaling.
    while bottom > top + 10:
        dark_pixels = sum(min(header.getpixel((x, bottom - 1))) < 245 for x in range(left, right))
        if dark_pixels < (right - left) * 0.75:
            break
        bottom -= 1
    return header.crop((left, top, right, bottom)).convert("RGBA")


@lru_cache(maxsize=1)
def _raster_ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise AmlError(
            "Für Raster-AML-Dateien fehlt die OCR-Abhängigkeit. "
            "Installiere die Pakete aus requirements.txt."
        ) from exc
    return RapidOCR()


def _normalize_ocr_text(text: str) -> str:
    return (
        text.replace("mm3/s", "mm³/s")
        .replace("�/s", "³/s")
        .replace("Â°C", "°C")
        .replace("�C", "°C")
        .strip()
    )


def _normalize_ocr_hex(text: str) -> str:
    candidate = text.strip().upper().replace("O", "0")
    match = HEX_RE.search(candidate)
    return match.group(0) if match else ""


def _ocr_raster(image: Image.Image, progress_callback: ProgressCallback | None = None) -> dict[str, str]:
    if progress_callback:
        progress_callback("OCR wird ausgeführt")
    results, _ = _raster_ocr_engine()(image.convert("RGB"))
    values: dict[str, str] = {}
    for box, text, confidence in results or []:
        if confidence < 0.55:
            continue
        x = min(point[0] for point in box)
        y = (min(point[1] for point in box) + max(point[1] for point in box)) / 2
        cleaned = _normalize_ocr_text(text)
        if y <= 130 and len(cleaned) > len(values.get("manufacturer", "")):
            values["manufacturer"] = cleaned
        elif 130 < y <= 205 and not values.get("material"):
            values["material"] = cleaned
        elif 130 < y <= 205 and _normalize_ocr_hex(cleaned):
            values["color_hex"] = _normalize_ocr_hex(cleaned)
        elif 205 < y <= 285:
            values["color"] = f"{values.get('color', '')} {cleaned}".strip()
        elif 365 < y <= 430 and x > 230:
            values["nozzle"] = cleaned
        elif 420 < y <= 480 and x > 230:
            values["bed"] = cleaned
        elif 470 < y <= 530 and x > 230:
            values["flow_ratio"] = cleaned
        elif 520 < y <= 585:
            match = re.search(r"(\d+(?:\.\d+)?\s*mm(?:³|3)/s)", cleaned, re.IGNORECASE)
            values["max_volumetric_speed"] = match.group(1) if match else cleaned

    # The long color line can be split into overlapping OCR boxes. Re-read its
    # fixed crop enlarged so names such as "Beige / Light Brown" stay intact.
    if progress_callback:
        progress_callback("Farbangabe wird ausgewertet")
    color_crop = image.convert("RGB").crop((0, 190, 700, 290)).resize((1400, 200))
    color_results, _ = _raster_ocr_engine()(color_crop)
    color_parts = [
        (min(point[0] for point in box), _normalize_ocr_text(text))
        for box, text, confidence in color_results or []
        if confidence >= 0.55
    ]
    if color_parts:
        values["color"] = " ".join(text for _x, text in sorted(color_parts)).strip()
    return values


def parse_aml(path: Path, progress_callback: ProgressCallback | None = None) -> AmlLabelData:
    if progress_callback:
        progress_callback("AML wird gelesen")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise AmlError(f"AML-Datei konnte nicht gelesen werden: {exc}") from exc

    if root.tag != "LPAPI":
        raise AmlError("Die Datei ist kein unterstütztes Labelife-AML-Dokument.")

    # Read text and vertical position together to distinguish header and color fields.
    text_entries = [
        (node.findtext("content", "").strip(), float(node.findtext("y", "999")))
        for node in root.findall(".//Text")
        if node.findtext("content", "").strip()
    ]
    texts = [text for text, _y in text_entries]
    color_hex = next((match.group(0).upper() for text in texts for match in [HEX_RE.search(text)] if match), "")
    nozzle, bed, flow_ratio, max_speed = _parse_measurements(texts)

    manufacturer = next((text for text, y in text_entries if y <= 2.0 and not HEX_RE.fullmatch(text)), "")
    candidates = [
        (text.replace("\n", " ").strip(), y)
        for text, y in text_entries
        if y > 2.0
        and not HEX_RE.fullmatch(text)
        and "Nozzle:" not in text
        and "Bed Temp:" not in text
        and "Flow Ratio:" not in text
        and "Max Vol Spd:" not in text
        and text != f"{nozzle}\n{bed}\n{flow_ratio}\n{max_speed}"
    ]
    material = next((text for text, _y in candidates if text.upper().startswith(MATERIAL_PREFIXES)), "")
    color = next((text for text, _y in candidates if text != material), "")

    qr_url = next((node.text.strip() for node in root.findall(".//Qrcode/webContent") if node.text and node.text.strip()), "")

    logo = None
    qr_image = None
    for node in root.findall(".//Image/content"):
        if not node.text:
            continue
        try:
            embedded = Image.open(io.BytesIO(base64.b64decode(node.text))).convert("RGBA")
            if embedded.size == (800, 600) and not texts and not qr_url:
                # Bulk exports flatten the complete label into one raster image.
                if progress_callback:
                    progress_callback("Rasterbild wird analysiert")
                raster_values = _ocr_raster(embedded, progress_callback)
                manufacturer = raster_values.get("manufacturer", "")
                material = raster_values.get("material", "")
                color = raster_values.get("color", "")
                color_hex = raster_values.get("color_hex", "")
                nozzle = raster_values.get("nozzle", "")
                bed = raster_values.get("bed", "")
                flow_ratio = raster_values.get("flow_ratio", "")
                max_speed = raster_values.get("max_volumetric_speed", "")
                logo = _crop_raster_logo(embedded)
                qr_image = embedded.crop((498, 298, 786, 586))
            else:
                logo = embedded
            break
        except (ValueError, OSError):
            continue

    return AmlLabelData(
        manufacturer,
        material,
        color,
        color_hex,
        nozzle,
        bed,
        flow_ratio,
        max_speed,
        qr_url,
        logo,
        qr_image,
    )


def _draw_right_aligned(draw: ImageDraw.ImageDraw, text: str, right: int, y: int, font, fill: str = "black") -> None:
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text((right - (bounds[2] - bounds[0]), y), text, font=font, fill=fill)


def _technical_layout(draw: ImageDraw.ImageDraw):
    available_width = 316 - 96
    gap = 5
    font = _font(14)
    while font.size > 7:
        widths = [draw.textbbox((0, 0), value, font=font)[2] for value in TECHNICAL_MAX_VALUES]
        if sum(widths) + gap * (len(widths) - 1) <= available_width:
            break
        font = _font(font.size - 1)

    widths = [draw.textbbox((0, 0), value, font=font)[2] for value in TECHNICAL_MAX_VALUES]
    positions = []
    x = 96
    for width in widths:
        positions.append(x)
        x += width + gap
    return font, positions


def _color_font(draw: ImageDraw.ImageDraw):
    available_width = 316 - 96
    gap = 8
    font = _font(16, bold=True)
    while font.size > 7:
        color_width = draw.textbbox((0, 0), "Texture Silver", font=font)[2]
        hex_width = draw.textbbox((0, 0), "#AABBCC", font=font)[2]
        if color_width + hex_width + gap <= available_width:
            return font
        font = _font(font.size - 1, bold=True)
    return font


def render_aml_to_png(
    source: Path, destination: Path, progress_callback: ProgressCallback | None = None
) -> AmlLabelData:
    data = parse_aml(source, progress_callback)
    if progress_callback:
        progress_callback("Label wird gerendert")
    image = Image.new("RGB", TARGET_SIZE, "white")
    draw = ImageDraw.Draw(image)

    qr_size = 84
    if data.qr_image:
        qr_image = data.qr_image.copy().convert("RGB")
        qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.NEAREST)
        image.paste(qr_image, (4, 6))
    elif data.qr_url:
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1, box_size=4)
        qr.add_data(data.qr_url)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.NEAREST)
        image.paste(qr_image, (4, 6))

    right_left = 96
    right_edge = 316
    if data.logo:
        logo = data.logo.copy()
        logo.thumbnail((135, 22), Image.Resampling.LANCZOS)
        image.paste(logo, (right_left, 3), logo)
    elif data.manufacturer:
        manufacturer_font = _fit_font(draw, data.manufacturer, right_edge - right_left, 16, bold=True)
        draw.text((right_left, 2), data.manufacturer, font=manufacturer_font, fill="black")

    bar_top = 26
    draw.rectangle((right_left, bar_top, right_edge, bar_top + 21), fill="black")
    material_font = _fit_font(draw, data.material or "Filament", 208, 15, bold=True)
    draw.text((right_left + 4, bar_top + 1), data.material or "Filament", font=material_font, fill="white")

    color_font = _color_font(draw)
    draw.text((right_left, 49), data.color or "Farbe", font=color_font, fill="black")
    if data.color_hex:
        _draw_right_aligned(draw, data.color_hex, right_edge, 49, color_font)

    # Size and columns are based on fixed maxima, not on the current label data.
    detail_font, _ = _technical_layout(draw)
    details = (
        data.nozzle or "-",
        data.bed or "-",
        data.flow_ratio or "-",
        data.max_volumetric_speed or "-",
    )
    draw.text((96, 72), details[0], font=detail_font, fill="black")
    draw.text((165, 72), details[1], font=detail_font, fill="black")
    draw.text((225, 72), details[2], font=detail_font, fill="black")
    _draw_right_aligned(draw, details[3], 316, 72, detail_font)

    image.save(destination, format="PNG")
    return data
