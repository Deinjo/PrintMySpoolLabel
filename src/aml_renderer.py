from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont


TARGET_SIZE = (320, 96)
HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
MATERIAL_PREFIXES = ("PLA", "PETG", "ABS", "ASA", "TPU", "PC", "PA", "PVA", "HIPS")


class AmlError(ValueError):
    pass


@dataclass(frozen=True)
class AmlLabelData:
    material: str
    color: str
    color_hex: str
    nozzle: str
    bed: str
    flow_ratio: str
    max_volumetric_speed: str
    qr_url: str
    logo: Image.Image | None


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


def parse_aml(path: Path) -> AmlLabelData:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise AmlError(f"AML-Datei konnte nicht gelesen werden: {exc}") from exc

    if root.tag != "LPAPI":
        raise AmlError("Die Datei ist kein unterstütztes Labelife-AML-Dokument.")

    texts = [node.text.strip() for node in root.findall(".//Text/content") if node.text and node.text.strip()]
    color_hex = next((match.group(0).upper() for text in texts for match in [HEX_RE.search(text)] if match), "")
    nozzle, bed, flow_ratio, max_speed = _parse_measurements(texts)

    candidates = [
        text.replace("\n", " ").strip()
        for text in texts
        if not HEX_RE.fullmatch(text)
        and "Nozzle:" not in text
        and "Bed Temp:" not in text
        and "Flow Ratio:" not in text
        and "Max Vol Spd:" not in text
        and text != f"{nozzle}\n{bed}\n{flow_ratio}\n{max_speed}"
    ]
    material = next((text for text in candidates if text.upper().startswith(MATERIAL_PREFIXES)), "")
    color = next((text for text in candidates if text != material), "")

    qr_url = next((node.text.strip() for node in root.findall(".//Qrcode/webContent") if node.text and node.text.strip()), "")

    logo = None
    for node in root.findall(".//Image/content"):
        if not node.text:
            continue
        try:
            logo = Image.open(io.BytesIO(base64.b64decode(node.text))).convert("RGBA")
            break
        except (ValueError, OSError):
            continue

    return AmlLabelData(material, color, color_hex, nozzle, bed, flow_ratio, max_speed, qr_url, logo)


def _draw_right_aligned(draw: ImageDraw.ImageDraw, text: str, right: int, y: int, font, fill: str = "black") -> None:
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text((right - (bounds[2] - bounds[0]), y), text, font=font, fill=fill)


def render_aml_to_png(source: Path, destination: Path) -> AmlLabelData:
    data = parse_aml(source)
    image = Image.new("RGB", TARGET_SIZE, "white")
    draw = ImageDraw.Draw(image)

    qr_size = 84
    if data.qr_url:
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

    bar_top = 28
    draw.rectangle((right_left, bar_top, right_edge, bar_top + 17), fill="black")
    material_font = _fit_font(draw, data.material or "Filament", 208, 13, bold=True)
    draw.text((right_left + 4, bar_top + 1), data.material or "Filament", font=material_font, fill="white")

    color_font = _fit_font(draw, data.color or "Farbe", 125, 11, bold=True)
    draw.text((right_left, 48), data.color or "Farbe", font=color_font, fill="black")
    if data.color_hex:
        hex_font = _fit_font(draw, data.color_hex, 90, 10, bold=True)
        _draw_right_aligned(draw, data.color_hex, right_edge, 49, hex_font)

    details = " | ".join(
        (
            data.nozzle or "-",
            data.bed or "-",
            data.flow_ratio or "-",
            data.max_volumetric_speed or "-",
        )
    )
    detail_font = _fit_font(draw, details, right_edge - right_left, 10)
    draw.text((right_left, 72), details, font=detail_font, fill="black")

    image.save(destination, format="PNG")
    return data
