"""Build the CSST 106 presentation (visual-first, minimal text) from the project's real outputs.

  python presentation/build_deck.py

Reads screenshots from presentation/screenshots/ (frontend/scripts/capture-screenshots.mjs) and
figures/metrics from ml/reports/ (ml/evaluate.py). Any result that does not exist yet is shown as a
clearly marked "pending" placeholder - re-run this script after evaluation to fill it in.
Speaker notes carry the details so the slides stay light.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "ml" / "reports"
SHOTS = ROOT / "presentation" / "screenshots"
LOGO = ROOT / "frontend" / "src" / "assets" / "aniroute-logo.png"
OUT = ROOT / "presentation" / "AniRoute_CSST106.pptx"

GREEN_DARK = RGBColor(0x17, 0x3C, 0x2D)
GREEN = RGBColor(0x1D, 0x65, 0x48)
GREEN_LIGHT = RGBColor(0xE7, 0xF1, 0xE8)
PAPER = RGBColor(0xF6, 0xF7, 0xF2)
INK = RGBColor(0x1E, 0x24, 0x1F)
MUTED = RGBColor(0x5D, 0x6A, 0x60)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
RED = RGBColor(0xDC, 0x26, 0x26)
PURPLE = RGBColor(0x7C, 0x3A, 0xED)
BLUE = RGBColor(0x25, 0x63, 0xEB)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height


def load_json(name: str) -> dict | None:
    try:
        return json.loads((REPORTS / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


METRICS = load_json("metrics.json")
LATENCY = load_json("latency.json")
OPTIMIZATION = load_json("optimization.json")
ABLATION = load_json("ablation.json")
MODEL_B = load_json("model_b.json")


def background(slide, color=PAPER):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def text(slide, x, y, w, h, value, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font="Segoe UI"):
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = Inches(0.05)
    lines = value if isinstance(value, list) else [value]
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = font
    return box


def rect(slide, x, y, w, h, fill=WHITE, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    item = slide.shapes.add_shape(shape, x, y, w, h)
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


def card_text(shape, lines, size=14, color=INK, bold_first=True, align=PP_ALIGN.LEFT):
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(0.15)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = line
        run.font.name = "Segoe UI"
        run.font.size = Pt(size if index else size + 2)
        run.font.bold = bold_first and index == 0
        run.font.color.rgb = color


def picture(slide, path: Path, x, y, w, h):
    """Place an image inside a box, keeping its aspect ratio (centred)."""
    if not path.exists():
        return pending(slide, x, y, w, h, f"Pending: {path.relative_to(ROOT).as_posix()}")
    with Image.open(path) as image:
        iw, ih = image.size
    scale = min(w / iw, h / ih)
    pw, ph = int(iw * scale), int(ih * scale)
    return slide.shapes.add_picture(str(path), x + (w - pw) // 2, y + (h - ph) // 2, pw, ph)


def crop_picture(slide, path: Path, x, y, w, h, top_fraction=0.0):
    """Fill a box with an image, cropping the overflow (used for tall full-page screenshots)."""
    if not path.exists():
        return pending(slide, x, y, w, h, f"Pending: {path.relative_to(ROOT).as_posix()}")
    with Image.open(path) as image:
        iw, ih = image.size
    pic = slide.shapes.add_picture(str(path), x, y, w, h)
    box_ratio, image_ratio = w / h, iw / ih
    if image_ratio < box_ratio:   # too tall → crop bottom (and an optional top offset)
        visible = image_ratio / box_ratio
        pic.crop_top = top_fraction
        pic.crop_bottom = max(0.0, 1 - visible - top_fraction)
    else:
        visible = box_ratio / image_ratio
        pic.crop_left = pic.crop_right = (1 - visible) / 2
    pic.line.color.rgb = RGBColor(0xD9, 0xDF, 0xD8)
    return pic


def pending(slide, x, y, w, h, message):
    box = rect(slide, x, y, w, h, fill=RGBColor(0xFF, 0xF7, 0xE6), line=AMBER)
    card_text(box, ["Result pending", message, "Re-run presentation/build_deck.py after ml/evaluate.py"], size=12,
              color=RGBColor(0x8A, 0x4D, 0x0C), align=PP_ALIGN.CENTER)
    return box


def title(slide, value, kicker=None):
    background(slide)
    if kicker:
        text(slide, Inches(0.6), Inches(0.35), Inches(8), Inches(0.35), kicker.upper(), size=11, bold=True, color=GREEN)
    text(slide, Inches(0.6), Inches(0.62), Inches(12), Inches(0.8), value, size=30, bold=True, color=GREEN_DARK, font="Segoe UI Semibold")


def notes(slide, value: str):
    slide.notes_slide.notes_text_frame.text = value


def fmt(value, digits=3):
    return "–" if value is None else f"{value:.{digits}f}"


def arrow(slide, x1, y1, x2, y2):
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    line.line.color.rgb = RGBColor(0x9B, 0xB3, 0xA2)
    line.line.width = Pt(2)
    line.line._get_or_add_ln().append(_arrow_head())
    return line


def _arrow_head():
    from pptx.oxml.ns import qn
    from lxml import etree
    tail = etree.SubElement(etree.Element(qn("a:ln")), qn("a:tailEnd"))
    tail.set("type", "triangle")
    return tail


# ---------------------------------------------------------------------------------------- slides
# 1 Title
s = prs.slides.add_slide(BLANK)
background(s, GREEN_DARK)
if LOGO.exists():
    text(s, Inches(0.8), Inches(0.6), Inches(6), Inches(0.4), "CSST 106 · FINAL PROJECT", size=12, bold=True, color=RGBColor(0x9C, 0xC9, 0xAE))
text(s, Inches(0.8), Inches(1.6), Inches(7), Inches(1.2), "AniRoute", size=60, bold=True, color=WHITE, font="Segoe UI Semibold")
text(s, Inches(0.8), Inches(2.9), Inches(6.2), Inches(1.4),
     "Real-time road-hazard detection for crop-aware farm-to-market delivery", size=24, color=RGBColor(0xDC, 0xEC, 0xE0))
text(s, Inches(0.8), Inches(5.9), Inches(6), Inches(0.5), "Computer vision · YOLO object detection · Agriculture & transportation",
     size=13, color=RGBColor(0x9C, 0xC9, 0xAE))
crop_picture(s, SHOTS / "02-vision-lab.png", Inches(7.4), Inches(1.0), Inches(5.4), Inches(5.5), top_fraction=0.18)
notes(s, "Team names. One sentence: AniRoute uses a phone or dashcam to detect road hazards with YOLO and re-routes "
         "perishable harvests away from them.")

# 2 Problem
s = prs.slides.add_slide(BLANK)
title(s, "Harvests lose value on the way to market", "Problem")
for index, (label, low, high, color) in enumerate([("Fruits", 5, 48, AMBER), ("Vegetables", 16, 40, RED)]):
    y = Inches(2.1 + index * 1.35)
    text(s, Inches(0.6), y, Inches(2), Inches(0.5), label, size=20, bold=True)
    track = rect(s, Inches(2.6), y, Inches(6.5), Inches(0.55), fill=RGBColor(0xE5, 0xE9, 0xE3), shape=MSO_SHAPE.RECTANGLE)
    span = rect(s, Inches(2.6 + 6.5 * low / 60), y, Inches(6.5 * (high - low) / 60), Inches(0.55), fill=color, shape=MSO_SHAPE.RECTANGLE)
    text(s, Inches(9.3), y, Inches(3.5), Inches(0.55), f"{low}–{high}% postharvest loss", size=18, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
text(s, Inches(0.6), Inches(4.7), Inches(12), Inches(1.2),
     ["Potholes, cracked pavement and obstructions on farm-to-market roads add bruising and delay.",
      "Drivers see hazards only when they reach them; route planners ignore how fragile the cargo is."], size=18, color=MUTED)
text(s, Inches(0.6), Inches(6.7), Inches(12), Inches(0.4),
     "Source: JICA, Data collection survey on the food value chain (Philippines) — openjicareport.jica.go.jp/pdf/1000035809.pdf",
     size=10, color=MUTED)
notes(s, "Quote the ranges, not a single number. Rough roads: World Bank Mindanao rural roads feature. "
         "The gap: no tool combines today's road condition with crop sensitivity.")

# 3 Objectives
s = prs.slides.add_slide(BLANK)
title(s, "What the system must do", "Objectives")
objectives = [("Detect", "Potholes, road damage and obstructions in real time"), ("See in poor light", "CLAHE preprocessing, measured"),
              ("Avoid false alarms", "Driving corridor + 2-of-3 frames"), ("Re-route", "Confirmed hazards raise route risk"),
              ("Prove it", "P, R, F1, mAP, confusion matrix")]
for index, (head, body) in enumerate(objectives):
    box = rect(s, Inches(0.6 + index * 2.5), Inches(2.3), Inches(2.3), Inches(3.0), fill=WHITE, line=RGBColor(0xDF, 0xE6, 0xDF))
    badge = rect(s, Inches(0.8 + index * 2.5), Inches(2.5), Inches(0.6), Inches(0.6), fill=GREEN, shape=MSO_SHAPE.OVAL)
    card_text(badge, [str(index + 1)], size=14, color=WHITE, align=PP_ALIGN.CENTER)
    text(s, Inches(0.75 + index * 2.5), Inches(3.3), Inches(2.0), Inches(0.5), head, size=18, bold=True, color=GREEN_DARK)
    text(s, Inches(0.75 + index * 2.5), Inches(3.9), Inches(2.0), Inches(1.3), body, size=14, color=MUTED)
notes(s, "Each objective maps to a later slide: detection (results), preprocessing (ablation), smoothing (Model B), "
         "routing (demo), evaluation.")

# 4 Significance
s = prs.slides.add_slide(BLANK)
title(s, "Who benefits", "Significance")
for index, (head, body) in enumerate([("Smallholder farmers", "Fewer bruised, spoiled harvests"), ("Haulers & drivers", "Early warning, smoother routes"),
                                      ("Cooperatives & traders", "Routes that weigh crop fragility"), ("LGU road maintenance", "Geotagged, photo-verified damage reports")]):
    col, row = index % 2, index // 2
    box = rect(s, Inches(0.6 + col * 6.2), Inches(2.0 + row * 2.3), Inches(5.9), Inches(2.0), fill=GREEN_LIGHT)
    card_text(box, [head, body], size=18, color=GREEN_DARK)
notes(s, "Concrete benefit per group. LGUs get a by-product: a map of confirmed road damage.")

# 5 System overview
s = prs.slides.add_slide(BLANK)
title(s, "System overview", "Architecture")
steps = [("Capture", "camera · video · image"), ("Preprocess", "EXIF · CLAHE · 640 px"), ("Model A", "fine-tuned YOLO\npotholes · cracks"),
         ("Model B", "pretrained COCO\nobstructions"), ("Filter", "threshold · corridor\n2 of 3 frames"), ("Confirm", "driver · GPS · evidence"),
         ("Re-route", "risk × crop sensitivity")]
positions = [(0.5, 3.0), (2.35, 3.0), (4.2, 2.0), (4.2, 4.0), (6.05, 3.0), (7.9, 3.0), (9.75, 3.0)]
centers = []
for (head, body), (x, y) in zip(steps, positions):
    fill = GREEN if head.startswith("Model") else WHITE
    box = rect(s, Inches(x), Inches(y), Inches(1.65), Inches(1.4), fill=fill, line=None if fill == GREEN else RGBColor(0xC9, 0xD6, 0xCB))
    card_text(box, [head, body], size=11, color=WHITE if fill == GREEN else GREEN_DARK, align=PP_ALIGN.CENTER)
    centers.append((Inches(x), Inches(y), Inches(1.65), Inches(1.4)))
links = [(0, 1), (1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (5, 6)]
for a, b in links:
    ax, ay, aw, ah = centers[a]
    bx, by, bw, bh = centers[b]
    arrow(s, ax + aw, ay + ah // 2, bx, by + bh // 2)
text(s, Inches(11.5), Inches(3.0), Inches(1.6), Inches(1.4), "Map + new route recommendation", size=12, bold=True, color=GREEN, anchor=MSO_ANCHOR.MIDDLE)
text(s, Inches(0.6), Inches(6.2), Inches(12), Inches(0.6),
     "Vue web app  →  FastAPI  →  OpenCV + Ultralytics YOLO (PyTorch / ONNX / OpenVINO, CPU)  →  OSRM routing  →  MapLibre map",
     size=13, color=MUTED)
notes(s, "Both models see the same preprocessed frame. Model B objects count only inside the driving corridor. "
         "Alerts need the hazard in 2 of the last 3 frames. Confirmed hazards within 75 m of a route raise its road risk.")

# 6 Dataset
s = prs.slides.add_slide(BLANK)
title(s, "Dataset: public, already labelled", "Dataset")
picture(s, REPORTS / "dataset_samples.png", Inches(0.6), Inches(1.6), Inches(7.4), Inches(5.3))
picture(s, REPORTS / "dataset_class_distribution.png", Inches(8.2), Inches(1.6), Inches(4.6), Inches(3.4))
stats = load_json("dataset_stats.json")
summary = (f"Images — train {stats['images_per_split'].get('train', 0)}, val {stats['images_per_split'].get('val', 0)}, "
           f"test {stats['images_per_split'].get('test', 0)}") if stats else "Roboflow pothole set + RDD2022 subset"
text(s, Inches(8.2), Inches(5.2), Inches(4.6), Inches(1.6),
     [summary, "D40 → pothole · D00/D10/D20 → severe road damage", "Near-duplicates removed from val/test"], size=13, color=MUTED)
notes(s, "Explain the YOLO label format, the 70/20/10 split, and why test images are never used for choices. "
         "Sources and licences in docs/DATASET.md.")

# 7 Preprocessing
s = prs.slides.add_slide(BLANK)
title(s, "Preprocessing: original vs processed", "Preprocessing")
before_after = REPORTS / "preprocessing_before_after.png"
if before_after.exists():
    picture(s, before_after, Inches(0.6), Inches(1.5), Inches(12.1), Inches(5.2))
else:
    crop_picture(s, SHOTS / "02-vision-lab.png", Inches(0.6), Inches(1.5), Inches(12.1), Inches(5.2), top_fraction=0.63)
text(s, Inches(0.6), Inches(6.8), Inches(12), Inches(0.5),
     "Orientation fix  ·  CLAHE on lightness when dark or low-contrast  ·  letterbox to 640 × 640 (no stretching)", size=14, color=MUTED)
notes(s, "CLAHE equalises the histogram per 8×8 tile with a clip limit of 2.0, on the LAB lightness channel only, so colours "
         "are unchanged. Auto mode applies it only when mean lightness < 95 or contrast < 38. Augmentation is separate (training only).")

# 8 CV method
s = prs.slides.add_slide(BLANK)
title(s, "Method: YOLO, fine-tuned + pretrained", "Computer vision method")
for index, (head, body) in enumerate([("Backbone", "edges, textures,\nshapes"), ("Neck", "multi-scale\nfeatures"), ("Head", "boxes · classes ·\nconfidence"), ("NMS", "keep best box\nper object")]):
    box = rect(s, Inches(0.6 + index * 3.1), Inches(1.7), Inches(2.6), Inches(1.4), fill=GREEN_LIGHT)
    card_text(box, [head, body], size=13, color=GREEN_DARK, align=PP_ALIGN.CENTER)
    if index < 3:
        arrow(s, Inches(3.2 + index * 3.1), Inches(2.4), Inches(3.7 + index * 3.1), Inches(2.4))
rows = [("", "Model A — road surface", "Model B — obstructions"),
        ("Weights", "COCO-pretrained → fine-tuned by us", "COCO-pretrained, used as-is"),
        ("Classes", "pothole · severe road damage", "person, animals, vehicles → obstruction"),
        ("Rule", "confidence ≥ threshold (max F1 on val)", "inside driving corridor and close"),
        ("Why", "road damage is not in COCO", "COCO already knows these objects")]
table = s.shapes.add_table(len(rows), 3, Inches(0.6), Inches(3.5), Inches(12.1), Inches(3.0)).table
for r, row in enumerate(rows):
    for c, value in enumerate(row):
        cell = table.cell(r, c)
        cell.text = value or " "
        paragraph = cell.text_frame.paragraphs[0]
        paragraph.runs[0].font.size = Pt(14)
        paragraph.runs[0].font.bold = r == 0 or c == 0
        paragraph.runs[0].font.color.rgb = WHITE if r == 0 else INK
        cell.fill.solid()
        cell.fill.fore_color.rgb = GREEN if r == 0 else (WHITE if r % 2 else GREEN_LIGHT)
notes(s, "One-stage detector: one forward pass. Transfer learning: keep the backbone's general features, retrain the head "
         "for our classes. E7 trains from scratch to show the benefit. Two-stage detectors are slower on a CPU.")

# 9 Implementation
s = prs.slides.add_slide(BLANK)
title(s, "The working application", "System implementation")
crop_picture(s, SHOTS / "02-vision-lab.png", Inches(0.6), Inches(1.5), Inches(6.3), Inches(5.4), top_fraction=0.0)
crop_picture(s, SHOTS / "05-active-trip.png", Inches(7.1), Inches(1.5), Inches(5.6), Inches(5.4), top_fraction=0.0)
notes(s, "Vision Lab: image, video and webcam with boxes, threshold slider and CLAHE toggle. Active trip: the camera or "
         "recorded drive is scanned; confirmed hazards re-score routes. Stack: Vue 3, FastAPI, OpenCV, Ultralytics.")

# 10 Results
s = prs.slides.add_slide(BLANK)
title(s, "Detections on images the model never saw", "Results")
gallery_tp = sorted((ROOT / "backend" / "samples").glob("test_*.jpg"))[:3]
if gallery_tp:
    for index, path in enumerate(gallery_tp):
        picture(s, path, Inches(0.6 + index * 4.1), Inches(1.6), Inches(3.9), Inches(4.6))
    text(s, Inches(0.6), Inches(6.4), Inches(12), Inches(0.5), "Held-out test images — run them live in the Vision Lab.", size=13, color=MUTED)
else:
    crop_picture(s, SHOTS / "02-vision-lab.png", Inches(0.6), Inches(1.5), Inches(12.1), Inches(5.3), top_fraction=0.22)
notes(s, "Point at class, confidence and model. Mention the obstruction example uses the pretrained model and the corridor rule.")

# 11 Evaluation
s = prs.slides.add_slide(BLANK)
title(s, "Evaluation on the test split", "Evaluation")
if METRICS:
    overall = METRICS["overall"]
    tiles = [("mAP@0.5", fmt(overall["map50"])), ("mAP@0.5:0.95", fmt(overall["map50_95"])), ("Precision", f"{overall['precision']:.0%}"),
             ("Recall", f"{overall['recall']:.0%}"), ("F1", fmt(overall["f1"]))]
    for index, (label, value) in enumerate(tiles):
        box = rect(s, Inches(0.6 + index * 2.45), Inches(1.5), Inches(2.25), Inches(1.3), fill=WHITE, line=RGBColor(0xDF, 0xE6, 0xDF))
        card_text(box, [value, label], size=13, color=GREEN_DARK, align=PP_ALIGN.CENTER)
    picture(s, REPORTS / "confusion_matrix.png", Inches(0.6), Inches(3.0), Inches(6.0), Inches(4.2))
    picture(s, REPORTS / "pr_curve.png", Inches(6.8), Inches(3.0), Inches(5.9), Inches(4.2))
    notes(s, f"Test split: {METRICS['dataset']['images']} images, {METRICS['dataset']['instances']} boxes. Threshold "
             f"{METRICS['operating_point']['confidence']} chosen on validation. Diagonal = correct; last column = misses; last row = false alarms.")
else:
    pending(s, Inches(0.6), Inches(1.6), Inches(12.1), Inches(5.2), "Train Model A, then: python ml/evaluate.py test")
    notes(s, "Metrics appear here after training and evaluation.")

# 12 Optimisation + speed
s = prs.slides.add_slide(BLANK)
title(s, "Optimisation: baseline → selected model", "Evaluation")
picture(s, REPORTS / "optimization_chart.png", Inches(0.6), Inches(1.5), Inches(6.2), Inches(4.6))
picture(s, REPORTS / "speed_chart.png", Inches(7.0), Inches(1.5), Inches(5.7), Inches(4.6))
line = "Selected run and accuracy gain appear after `evaluate.py compare`."
if OPTIMIZATION:
    training = [row for row in OPTIMIZATION["rows"] if row.get("kind") == "training"]
    base = next((row for row in training if row["id"] == "E0"), training[0])
    best = next(row for row in training if row["id"] == OPTIMIZATION["selected"])
    line = f"E0 mAP@0.5 {base['map50']:.3f} → {best['id']} {best['map50']:.3f} (validation)"
if LATENCY and LATENCY.get("system"):
    line += f"  ·  end-to-end {LATENCY['system']['fps']} FPS on laptop CPU"
text(s, Inches(0.6), Inches(6.3), Inches(12), Inches(0.6), line, size=15, bold=True, color=GREEN_DARK)
notes(s, "One change per experiment: longer training, bigger model, higher resolution, augmentation; E5 threshold, "
         "E6 CLAHE. Speed: OpenVINO/ONNX vs PyTorch on the same CPU.")

# 13 Error analysis
s = prs.slides.add_slide(BLANK)
title(s, "Where it fails, and why", "Error analysis")
gallery = REPORTS / "error_gallery"
examples = []
for kind in ("false_negatives", "false_positives", "misclassified"):
    examples += sorted((gallery / kind).glob("*.jpg"))[:1]
captions = {}
try:
    captions = json.loads((gallery / "captions.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    pass
if examples:
    for index, path in enumerate(examples[:3]):
        picture(s, path, Inches(0.6 + index * 4.1), Inches(1.6), Inches(3.9), Inches(3.9))
        caption = captions.get(f"{path.parent.name}/{path.name}", path.parent.name.replace("_", " "))
        text(s, Inches(0.6 + index * 4.1), Inches(5.6), Inches(3.9), Inches(0.9), caption, size=12, color=MUTED, align=PP_ALIGN.CENTER)
else:
    pending(s, Inches(0.6), Inches(1.6), Inches(12.1), Inches(4.8), "Error gallery is produced by ml/evaluate.py test")
if METRICS:
    sizes = METRICS["error_breakdown"]["miss_rate_by_size"]
    parts = [f"{name}: {row['miss_rate']:.0%}" for name, row in sizes.items() if row["miss_rate"] is not None]
    text(s, Inches(0.6), Inches(6.6), Inches(12), Inches(0.5), "Miss rate by object size — " + " · ".join(parts), size=14, bold=True, color=GREEN_DARK)
notes(s, "White = ground truth, yellow frame = the error. Explain the cause of each: small/distant pothole, shadow or wet "
         "asphalt, crack vs pothole confusion.")

# 14 Demo divider
s = prs.slides.add_slide(BLANK)
background(s, GREEN_DARK)
text(s, Inches(0.8), Inches(2.6), Inches(11.7), Inches(1.2), "Live demonstration", size=48, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
text(s, Inches(0.8), Inches(3.9), Inches(11.7), Inches(0.8), "Vision Lab  →  recorded drive  →  plan  →  active trip  →  confirm  →  re-route  →  evaluation",
     size=18, color=RGBColor(0xDC, 0xEC, 0xE0), align=PP_ALIGN.CENTER)
notes(s, "Follow docs/DEMO_SCRIPT.md. Backup: screenshots in presentation/screenshots/.")

# 15 Limitations
s = prs.slides.add_slide(BLANK)
title(s, "Limitations", "Honest assessment")
limits = [("Foreign training data", "RDD2022 and Roboflow roads differ from Philippine farm roads"),
          ("No standing-water model", "Flooded-road data is scarce; drivers report it"),
          ("COCO gaps", "No carabao, goat, fallen tree or landslide class"),
          ("Hard conditions", "Small potholes, night, rain and blur reduce recall"),
          ("Heuristic route weights", "Not validated loss figures; needs field trials"),
          ("No distance estimate", "Hazard pinned at the vehicle's GPS position")]
for index, (head, body) in enumerate(limits):
    col, row = index % 2, index // 2
    box = rect(s, Inches(0.6 + col * 6.2), Inches(1.6 + row * 1.75), Inches(5.9), Inches(1.5), fill=WHITE, line=RGBColor(0xDF, 0xE6, 0xDF))
    card_text(box, [head, body], size=14, color=INK)
notes(s, "Be specific and link each limitation to evidence (error gallery, robustness table, test_local result if available).")

# 16 Real-world use & future work
s = prs.slides.add_slide(BLANK)
title(s, "Real-world use and next steps", "Application")
crop_picture(s, SHOTS / "05-active-trip-mobile.png", Inches(0.6), Inches(1.5), Inches(3.0), Inches(5.6), top_fraction=0.0)
for index, (head, body) in enumerate([("Today", "Phone on the dashboard warns the driver and re-checks the route"),
                                      ("Next", "Label local Philippine road images; add standing-water class"),
                                      ("Then", "On-device inference (ONNX/TFLite); shared hazard map for LGUs"),
                                      ("Validate", "Field trial measuring spoilage with and without AniRoute")]):
    box = rect(s, Inches(4.0), Inches(1.5 + index * 1.42), Inches(8.7), Inches(1.25), fill=GREEN_LIGHT if index == 0 else WHITE,
               line=None if index == 0 else RGBColor(0xDF, 0xE6, 0xDF))
    card_text(box, [head, body], size=15, color=GREEN_DARK)
notes(s, "Close with impact: fewer damaged harvests, safer drivers, and a living map of farm-to-market road conditions.")

# 17 Thank you
s = prs.slides.add_slide(BLANK)
background(s, GREEN_DARK)
text(s, Inches(0.8), Inches(2.7), Inches(11.7), Inches(1.2), "Thank you", size=54, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
text(s, Inches(0.8), Inches(4.0), Inches(11.7), Inches(0.8), "Questions?", size=24, color=RGBColor(0xDC, 0xEC, 0xE0), align=PP_ALIGN.CENTER)
notes(s, "See docs/DEFENSE_QA.md for prepared answers.")

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print(f"wrote {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)"
      + ("" if METRICS else " — evaluation pending: placeholders shown on slides 11-13"))
