import io

from PIL import Image, ImageDraw, ImageFont

from app.rag.ocr import ocr_engine


def _render_text_image(text: str) -> bytes:
    image = Image.new("RGB", (600, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    draw.text((10, 30), text, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_real_ocr_extracts_text_from_a_rendered_image():
    image_bytes = _render_text_image("INSPECTION REQUIRED")
    text, confidence = ocr_engine.extract_text(image_bytes)
    assert "INSPECTION" in text.upper()
    assert confidence > 0.0


def test_blank_image_yields_empty_text():
    blank = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    text, confidence = ocr_engine.extract_text(buf.getvalue())
    assert text == ""
    assert confidence == 0.0
