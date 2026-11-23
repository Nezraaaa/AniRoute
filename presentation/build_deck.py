"""Build the CSST 106 presentation from the project's real outputs.

  python presentation/build_deck.py

Design rules:
- Canva-friendly. The deck uses only text boxes, basic shapes, plain pictures and solid backgrounds, in
  Outfit and DM Sans (both built into Canva; installable copies are in presentation/fonts/).
- Light on text: a few words per item, with details in the speaker notes.
- Images are fitted whole and never cropped.
- Amber labels highlight what to look at.
- Each slide's speaker notes hold its script from presentation/SPEAKER_SCRIPT.md.

Inputs:
- Figures and metrics from ml/reports/ (ml/evaluate.py).
- App captures from presentation/video/assets/ (presentation/video/capture-assets.mjs).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "ml" / "reports"
APP = ROOT / "presentation" / "screenshots" / "deck"   # app captures (capture-assets.mjs, ANIROUTE_ASSET_DIR)
DETECTIONS = REPORTS / "sample_detections"
CRACK = REPORTS / "crack"                  # crack-class figures (ml/scripts/crack_report.py)
CORRECT = REPORTS / "correct_detections"   # verified correct detections (ml/scripts/select_correct_detections.py)
OUT = ROOT / "presentation" / "AniRoute_CSST106.pptx"
SCRIPT_FILE = ROOT / "presentation" / "SPEAKER_SCRIPT.md"

TITLE_FONT, BODY_FONT = "Outfit", "DM Sans"
GREEN_DARK = RGBColor(0x17, 0x3C, 0x2D)
GREEN = RGBColor(0x1D, 0x65, 0x48)
GREEN_LIGHT = RGBColor(0xE7, 0xF1, 0xE8)
PAPER = RGBColor(0xF6, 0xF7, 0xF2)
INK = RGBColor(0x1E, 0x24, 0x1F)
MUTED = RGBColor(0x5D, 0x6A, 0x60)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xF5, 0xB0, 0x2E)
AMBER_INK = RGBColor(0x3D, 0x2A, 0x05)
ORANGE = RGBColor(0xF9, 0x73, 0x16)
RED = RGBColor(0xDC, 0x26, 0x26)
LINE = RGBColor(0xDF, 0xE6, 0xDF)
SOFT_GREEN_TEXT = RGBColor(0xDC, 0xEC, 0xE0)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def load_json(name: str) -> dict | None:
    try:
        return json.loads((REPORTS / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


METRICS = load_json("metrics.json")
HIGH_CONF = load_json("high_confidence_profile.json")
LATENCY = load_json("latency.json")
OPTIMIZATION = load_json("optimization.json")
STATS = load_json("dataset_stats.json")
CRACK_METRICS = json.loads((REPORTS / "crack" / "crack_metrics.json").read_text(encoding="utf-8"))
CRACK_EVAL = (METRICS or {}).get("per_class", {}).get("severe_road_damage", {})


def load_script() -> dict[int, str]:
    try:
        source = SCRIPT_FILE.read_text(encoding="utf-8")
    except OSError:
        return {}
    parts = re.split(r"^## Slide (\d+)[^\n]*\n", source, flags=re.M)
    script = {}
    for number, body in zip(parts[1::2], parts[2::2]):
        body = body.split("\n---")[0]
        script[int(number)] = re.sub(r"\*\*|`", "", body).strip()
    return script


SCRIPT = load_script()


# ------------------------------------------------------------------------------------------ helpers
def new_slide(bg=PAPER):
    slide = prs.slides.add_slide(BLANK)
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = bg
    return slide


def text(slide, x, y, w, h, value, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=BODY_FONT):
    box_ = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box_.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = Inches(0.04)
    frame.margin_top = frame.margin_bottom = Inches(0.02)
    for index, line in enumerate(value if isinstance(value, list) else [value]):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = line
        run.font.size, run.font.bold, run.font.name = Pt(size), bold, font
        run.font.color.rgb = color
    return box_


def box(slide, x, y, w, h, fill=WHITE, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12):
    item = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    item.fill.solid()
    item.fill.fore_color.rgb = fill
    if line is None:
        item.line.fill.background()
    else:
        item.line.color.rgb = line
        item.line.width = Pt(1)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        item.adjustments[0] = radius
    item.shadow.inherit = False
    return item


def fill_text(shape, lines, size=16, color=INK, align=PP_ALIGN.CENTER, first_bold=True, first_font=TITLE_FONT):
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = frame.margin_right = Inches(0.1)
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = line
        first = index == 0
        run.font.name = first_font if first else BODY_FONT
        run.font.size = Pt(size + (3 if first and len(lines) > 1 else 0))
        run.font.bold = first_bold and first
        run.font.color.rgb = color


def card(slide, x, y, w, h, head, body=None, fill=WHITE, color=GREEN_DARK, size=15):
    item = box(slide, x, y, w, h, fill=fill, line=LINE if fill == WHITE else None)
    fill_text(item, [head] + ([body] if body else []), size=size, color=color)
    return item


def pill(slide, x, y, label, fill=AMBER, color=AMBER_INK, size=13, center=False):
    """A short highlight label. Width follows the text; (x, y) is the top-left, or the centre if center=True."""
    width = 0.4 + len(label) * size * 0.0095
    height = 0.2 + size * 0.0185
    if center:
        x, y = x - width / 2, y - height / 2
    item = box(slide, x, y, width, height, fill=fill, radius=0.5)
    fill_text(item, [label], size=size, color=color, first_font=BODY_FONT)
    return item


def title(slide, value, kicker=None):
    if kicker:
        text(slide, 0.6, 0.38, 9, 0.35, kicker.upper(), size=12, bold=True, color=GREEN)
    text(slide, 0.6, 0.66, 12.1, 0.8, value, size=30, bold=True, color=GREEN_DARK, font=TITLE_FONT)


def picture(slide, path: Path, x, y, w, h, border=True):
    """Fit the whole image inside the box (never cropped). Returns the placed (x, y, w, h) in inches."""
    if not path.exists():
        item = box(slide, x, y, w, h, fill=RGBColor(0xFF, 0xF7, 0xE6), line=AMBER)
        fill_text(item, ["Missing image", path.name], size=12, color=AMBER_INK)
        return x, y, w, h
    with Image.open(path) as image:
        iw, ih = image.size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    px, py = x + (w - pw) / 2, y + (h - ph) / 2
    pic = slide.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(0.75)
    return px, py, pw, ph


def label_on(slide, geom, fx, fy, label, number=None, size=13):
    """Highlight label centred on a fractional point (fx, fy) of a placed picture."""
    px, py, pw, ph = geom
    pill(slide, px + fx * pw, py + fy * ph, f"{number}  {label}" if number else label, center=True, size=size)


def arrow(slide, x, y, w=0.34, h=0.32, color=RGBColor(0x9B, 0xB3, 0xA2)):
    return box(slide, x, y, w, h, fill=color, shape=MSO_SHAPE.RIGHT_ARROW)


def notes(slide, fallback: str):
    slide.notes_slide.notes_text_frame.text = SCRIPT.get(len(prs.slides), fallback)


def pct(v):
    return f"{v:.0%}"


# ------------------------------------------------------------------------------------------ slides
# 1 Title
s = new_slide(GREEN_DARK)
text(s, 0.8, 0.7, 6.5, 0.4, "CSST 106 · FINAL PROJECT", size=13, bold=True, color=RGBColor(0x9C, 0xC9, 0xAE))
text(s, 0.8, 1.7, 6.6, 1.2, "AniRoute", size=66, bold=True, color=WHITE, font=TITLE_FONT)
text(s, 0.8, 3.0, 6.2, 1.4, "Road-hazard detection for farm-to-market delivery", size=26, color=SOFT_GREEN_TEXT, font=TITLE_FONT)
text(s, 0.8, 5.9, 6.4, 0.5, "Computer vision · Agriculture · Transportation", size=14, color=RGBColor(0x9C, 0xC9, 0xAE))
g = picture(s, CORRECT / "severe_road_damage_3_62.jpg", 7.5, 0.9, 5.2, 5.6, border=False)
label_on(s, g, 0.5, 0.07, "Our model: cracks found on an unseen road")
notes(s, "Title.")

# 2 Problem
s = new_slide()
title(s, "Harvests lose value on the way to market", "Problem")
for index, (label, low, high, color) in enumerate([("Fruits", 5, 48, AMBER), ("Vegetables", 16, 40, RED)]):
    y = 2.0 + index * 1.25
    text(s, 0.6, y + 0.05, 2.0, 0.5, label, size=20, bold=True, font=TITLE_FONT)
    box(s, 2.6, y, 6.5, 0.55, fill=RGBColor(0xE5, 0xE9, 0xE3), shape=MSO_SHAPE.RECTANGLE)
    box(s, 2.6 + 6.5 * low / 60, y, 6.5 * (high - low) / 60, 0.55, fill=color, shape=MSO_SHAPE.RECTANGLE)
    text(s, 9.3, y, 3.6, 0.55, f"{low}–{high}% lost", size=20, bold=True, anchor=MSO_ANCHOR.MIDDLE, font=TITLE_FONT)
card(s, 0.6, 4.75, 5.9, 1.2, "Rough roads", "bruising and delays", fill=GREEN_LIGHT)
card(s, 6.8, 4.75, 5.9, 1.2, "Hazards seen too late", "routes ignore fragile cargo", fill=GREEN_LIGHT)
text(s, 0.6, 6.75, 12, 0.4, "Source: JICA food value chain survey, Philippines (postharvest loss ranges)", size=11, color=MUTED)
notes(s, "Problem.")

# 3 Objectives
s = new_slide()
title(s, "What the system must do", "Objectives")
objectives = [("Detect", "road cracks, live"), ("Preprocess", "test what helps"), ("Fewer false alarms", "threshold + 2 of 3 frames"),
              ("Re-route", "confirmed hazards raise risk"), ("Evaluate", "P · R · F1 · mAP")]
for index, (head, body) in enumerate(objectives):
    x = 0.6 + index * 2.5
    box(s, x, 2.2, 2.3, 3.1, fill=WHITE, line=LINE)
    badge = box(s, x + 0.2, 2.42, 0.62, 0.62, fill=GREEN, shape=MSO_SHAPE.OVAL)
    fill_text(badge, [str(index + 1)], size=16, color=WHITE)
    text(s, x + 0.15, 3.25, 2.0, 0.9, head, size=19, bold=True, color=GREEN_DARK, font=TITLE_FONT)
    text(s, x + 0.15, 4.15, 2.0, 1.0, body, size=15, color=MUTED)
notes(s, "Objectives.")

# 4 Significance
s = new_slide()
title(s, "Who benefits", "Significance")
for index, (head, body) in enumerate([("Farmers", "fewer bruised harvests"), ("Drivers", "early hazard warning"),
                                      ("Cooperatives", "routes that respect the crop"), ("Local government", "photo-verified road damage map")]):
    col, row = index % 2, index // 2
    card(s, 0.6 + col * 6.2, 2.0 + row * 2.3, 5.9, 2.0, head, body, fill=GREEN_LIGHT, size=18)
notes(s, "Significance.")

# 5 System overview
s = new_slide()
title(s, "How AniRoute works", "System overview")
steps = [("Capture", "camera or video"), ("Prepare", "orient · 640 px"), ("Our model", "cracked road"),
         ("Filter", "0.40 · 2 of 3 frames"), ("Confirm", "tap or voice"), ("Re-route", "crop-aware risk")]
for index, (head, body) in enumerate(steps):
    x = 0.55 + index * 2.12
    is_model = head == "Our model"
    card(s, x, 2.6, 1.7, 1.7, head, body, fill=GREEN if is_model else WHITE, color=WHITE if is_model else GREEN_DARK, size=14)
    if index < len(steps) - 1:
        arrow(s, x + 1.74, 3.29)
pill(s, 0.55 + 2 * 2.12 + 0.85, 4.75, "Trained by us", center=True)
text(s, 0.6, 6.2, 12.1, 0.5, "Web app · FastAPI · YOLO11 · OSRM roads · MapLibre map — runs on a laptop CPU", size=14, color=MUTED, align=PP_ALIGN.CENTER)
notes(s, "System overview.")

# 6 Dataset
s = new_slide()
title(s, "Dataset: labelled road images", "Dataset")
picture(s, CRACK / "dataset_crack_samples.jpg", 0.6, 1.95, 8.2, 4.1)
pill(s, 0.6 + 8.2 / 2, 1.72, "Red boxes = cracks drawn by human labellers", center=True)
split = STATS["images_per_split"] if STATS else {"train": 1800, "val": 448, "test": 444}
total = sum(split.get(k, 0) for k in ("train", "val", "test"))
for index, (head, body) in enumerate([(f"{total:,}", "labelled road images"),
                                      (f"{split.get('train', 0):,} / {split.get('val', 0)} / {split.get('test', 0)}", "train / validation / test"),
                                      ("3 crack types", "along · across · alligator")]):
    card(s, 9.1, 1.95 + index * 1.42, 3.65, 1.25, head, body, fill=GREEN_LIGHT, size=16)
text(s, 0.6, 6.35, 12.1, 0.5, "RDD2022 road damage dataset, India subset (CC BY 4.0) · test images never used for training", size=13, color=MUTED)
notes(s, "Dataset.")

# 7 Preprocessing
s = new_slide()
title(s, "Preparing each frame", "Preprocessing")
g = picture(s, REPORTS / "preprocessing_before_after.png", 0.6, 1.95, 5.6, 5.3)
for fx, label in [(1 / 6, "Original"), (0.5, "CLAHE"), (5 / 6, "Model input")]:
    label_on(s, g, fx, -0.035, label, size=10)
for index, (head, body) in enumerate([("Orientation fix", "photos upright"), ("Letterbox 640 × 640", "no stretching"),
                                      ("CLAHE tested", "lowered accuracy → kept off")]):
    card(s, 6.6, 1.75 + index * 1.8, 6.1, 1.5, head, body, fill=GREEN_LIGHT if index < 2 else WHITE, size=18)
notes(s, "Preprocessing.")

# 8 Our model
s = new_slide()
title(s, "Our model: YOLO11 trained for road damage", "Computer vision method")
for index, (head, body) in enumerate([("Backbone", "edges · textures"), ("Neck", "multi-scale"), ("Head", "box · class · score"), ("NMS", "best box")]):
    x = 0.6 + index * 3.15
    card(s, x, 1.75, 2.6, 1.45, head, body, fill=GREEN_LIGHT, size=16)
    if index < 3:
        arrow(s, x + 2.68, 2.3)
facts = [("1,800", "road images we trained on"), ("3 crack types", "along · across · alligator"), ("40 epochs", "early stopping"), ("0.40", "app confidence threshold")]
for index, (head, body) in enumerate(facts):
    card(s, 0.6 + index * 3.15, 3.85, 2.85, 2.0, head, body, size=20)
pill(s, 0.6, 6.25, "One pass per frame → real time on a laptop CPU", fill=GREEN, color=WHITE)
notes(s, "Our model.")

# 9 The working app
s = new_slide()
title(s, "The working application", "System implementation")
g1 = picture(s, APP / "plan-routes.png", 0.5, 1.55, 7.6, 5.3)
label_on(s, g1, 0.14, 0.42, "Crop & load", "1")
label_on(s, g1, 0.62, 0.34, "3 route options", "2")
label_on(s, g1, 0.75, 0.82, "Live road map", "3")
g2 = picture(s, APP / "camera-card.png", 8.4, 1.55, 4.45, 5.3)
label_on(s, g2, 0.5, 0.40, "Live road camera", "4")
label_on(s, g2, 0.5, 0.86, "Detects cracks", "5")
notes(s, "Implementation.")

# 10 Results: a correct crack detection on an unseen road, and what that looks like across the test set
s = new_slide()
title(s, "Our model finds cracks on roads it never saw", "Results")


def zoom_image(name: str, out_name: str, size: int = 700) -> Path:
    """Square close-up of the damaged surface inside the example's detection box."""
    summary = json.loads((CORRECT / "summary.json").read_text(encoding="utf-8"))
    entry = next(item for item in summary["picked"] if item["file"] == name)
    box_ = max(entry["boxes"], key=lambda b: b["confidence"])["box"]
    with Image.open(CORRECT / name) as image:
        w, h = image.size
        cx, cy = (box_[0] + box_[2]) / 2, (box_[1] + box_[3]) / 2
        side = min(max(min(box_[2] - box_[0], box_[3] - box_[1]) * 0.95, 160), min(w, h))
        x0, y0 = min(max(0, cx - side / 2), w - side), min(max(0, cy - side / 2), h - side)
        out = CORRECT / out_name
        image.crop((int(x0), int(y0), int(x0 + side), int(y0 + side))).resize((size, size), Image.LANCZOS).save(out, quality=92)
    return out


g = picture(s, CORRECT / "severe_road_damage_3_62.jpg", 0.6, 1.65, 4.2, 4.2, border=False)
label_on(s, g, 0.5, 0.07, "✓ Crack detected · 62%", size=14)
zoom = zoom_image("severe_road_damage_3_62.jpg", "zoom_severe_road_damage_3_62.jpg")
gz = picture(s, zoom, 4.95, 1.65, 2.35, 2.35)
label_on(s, gz, 0.5, 0.1, "Zoom: the cracks", size=11)
text(s, 4.95, 4.15, 2.4, 1.6, ["Green = our model", "Dashed = human label", "They line up."], size=13, color=MUTED)
app = CRACK_METRICS["at_app_threshold"]
picture(s, CRACK / "result_counts.png", 7.6, 1.65, 5.15, 2.9)
for index, (value, label) in enumerate([(pct(app["precision"]), "of crack alerts are real"), (str(app["correct"]), "correct alerts"),
                                        (str(app["false_alarms"]), "false alarms")]):
    card(s, 7.6 + index * 1.75, 4.75, 1.6, 1.15, value, label, fill=GREEN_LIGHT if index == 0 else WHITE, size=13)
pill(s, 13.333 / 2, 6.45, f"At the app's {app['threshold']:.0%} threshold: few false alarms, but many cracks still missed", fill=GREEN, color=WHITE, size=14, center=True)
notes(s, "Results.")

# 11 Evaluation (crack class, held-out test split)
s = new_slide()
title(s, "Evaluation: cracks on 444 held-out images", "Evaluation")
app = CRACK_METRICS["at_app_threshold"]
tiles = [(f"{CRACK_EVAL.get('ap50', CRACK_METRICS['ap50']):.3f}", "AP@0.5"), (f"{CRACK_EVAL.get('ap50_95', 0):.3f}", "AP@0.5:0.95"),
         (pct(app["precision"]), "Precision"), (pct(app["recall"]), "Recall"), (f"{app['f1']:.2f}", "F1")]
for index, (value, label) in enumerate(tiles):
    card(s, 0.6 + index * 2.45, 1.55, 2.25, 1.25, value, label, fill=GREEN_LIGHT if index >= 2 else WHITE, size=18)
pill(s, 0.6 + 3 * 2.45 + 1.1, 3.05, f"At threshold {app['threshold']:.2f} · precision is not accuracy", center=True)
picture(s, CRACK / "pr_curve.png", 0.6, 3.45, 5.9, 3.7)
picture(s, CRACK / "threshold_chart.png", 6.85, 3.45, 5.9, 3.7)
notes(s, "Evaluation.")

# 12 Optimisation and speed
s = new_slide()
title(s, "Making it better and faster", "Evaluation")
picture(s, REPORTS / "optimization_chart.png", 0.6, 2.05, 6.1, 4.6)
picture(s, REPORTS / "speed_chart.png", 6.95, 2.05, 5.8, 4.6)
gain = "E0 → E1: +16% mAP (validation)"
if OPTIMIZATION:
    training = [row for row in OPTIMIZATION["rows"] if row.get("kind") == "training"]
    base = next((row for row in training if row["id"] == "E0"), training[0])
    best = next(row for row in training if row["id"] == OPTIMIZATION["selected"])
    gain = f"Longer training ({base['id']} → {best['id']}): +{(best['map50'] / base['map50'] - 1):.0%} validation mAP"
fps = LATENCY["system"]["fps"] if LATENCY and LATENCY.get("system") else None
pill(s, 0.6, 1.5, gain)
pill(s, 6.95, 1.5, f"OpenVINO fastest · {fps:.0f} FPS end to end" if fps else "OpenVINO fastest")
notes(s, "Optimisation.")

# 13 Error analysis (crack examples from the test-split error gallery)
s = new_slide()
title(s, "Where it fails, and why", "Error analysis")
gallery = REPORTS / "error_gallery"
for index, (name, label) in enumerate((("false_negatives/01_data_002610.jpg", "Missed"), ("false_positives/02_data_002521.jpg", "False alarm"),
                                       ("false_positives/06_data_002678.jpg", "Right crack, box drawn differently"))):
    g = picture(s, gallery / name, 0.6 + index * 4.1, 1.6, 3.9, 3.9, border=False)
    label_on(s, g, 0.5, 0.07, label, size=13 if index < 2 else 12)
text(s, 0.6, 5.65, 12.1, 0.5, "White = human label · red = our model · yellow frame = the error", size=13, color=MUTED, align=PP_ALIGN.CENTER)
sizes = CRACK_METRICS["miss_rate_by_size_at_app_threshold"]
large_found = 1 - (sizes["large"]["miss_rate"] or 0)
pill(s, 13.333 / 2, 6.45, f"Large, clear cracks are found most ({large_found:.0%}); thin or distant ones are usually missed", fill=GREEN, color=WHITE, size=14, center=True)
notes(s, "Error analysis.")

# 14 Demo
s = new_slide(GREEN_DARK)
text(s, 0.8, 2.4, 11.7, 1.2, "Live demonstration", size=52, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font=TITLE_FONT)
for index, step in enumerate(["Plan", "Drive", "Detect", "Confirm", "Re-route"]):
    chip = box(s, 2.05 + index * 1.9, 4.0, 1.6, 0.6, fill=RGBColor(0x24, 0x55, 0x40), radius=0.5)
    fill_text(chip, [step], size=15, color=WHITE, first_font=BODY_FONT)
notes(s, "Demo.")

# 15 Limitations
s = new_slide()
title(s, "Limitations", "Honest assessment")
recall = pct(HIGH_CONF["test"]["recall"]) if HIGH_CONF else "low"
recall = pct(CRACK_METRICS["at_app_threshold"]["recall"])
limits = [("Cracks only", "other damage types need more labelled data"), ("Low recall at 0.40", f"finds {recall} of cracks"),
          ("Foreign training data", "Indian roads, not Philippine"), ("Obstructions out of scope", "people, animals, trees"),
          ("Heuristic route weights", "needs field trials"), ("No distance estimate", "pinned at vehicle GPS")]
for index, (head, body) in enumerate(limits):
    col, row = index % 2, index // 2
    card(s, 0.6 + col * 6.2, 1.65 + row * 1.75, 5.9, 1.5, head, body, size=16)
notes(s, "Limitations.")

# 16 Next steps
s = new_slide()
title(s, "Real-world use and next steps", "Application")
picture(s, APP / "phone-trip.png", 0.6, 1.5, 3.0, 5.6)
for index, (head, body) in enumerate([("Today", "phone on the dashboard warns the driver"), ("Next", "more damage types · Philippine road images"),
                                      ("Then", "on-phone model · shared hazard map"), ("Validate", "field trial on spoilage")]):
    card(s, 4.0, 1.55 + index * 1.4, 8.7, 1.2, head, body, fill=GREEN_LIGHT if index == 0 else WHITE, size=16)
notes(s, "Next steps.")

# 17 Thank you
s = new_slide(GREEN_DARK)
text(s, 0.8, 2.6, 11.7, 1.2, "Thank you", size=58, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font=TITLE_FONT)
text(s, 0.8, 3.95, 11.7, 0.8, "Questions?", size=26, color=SOFT_GREEN_TEXT, align=PP_ALIGN.CENTER, font=TITLE_FONT)
notes(s, "Q&A.")

OUT.parent.mkdir(parents=True, exist_ok=True)
try:
    prs.save(OUT)
except PermissionError:   # the deck is open in PowerPoint: save next to it instead of failing
    OUT = OUT.with_name(OUT.stem + "_updated.pptx")
    prs.save(OUT)
    print("The main deck is open in PowerPoint; saved the new version next to it.")
print(f"wrote {OUT.relative_to(ROOT)} ({len(prs.slides)} slides, notes from {SCRIPT_FILE.name}: {len(SCRIPT)} slides)")
