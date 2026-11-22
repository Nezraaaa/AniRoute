"""Object-detection metrics implemented from scratch with NumPy.

Implementing them ourselves (instead of only reading Ultralytics' summary) lets us
evaluate *exactly* the app's pipeline (our preprocessing + letterbox) and produce
per-image error records for the error-analysis gallery.

Definitions used throughout (IoU = intersection over union of two boxes):
- A prediction is a true positive (TP) when it overlaps an unmatched ground-truth box
  of the same class with IoU >= threshold; otherwise it is a false positive (FP).
- A ground-truth box with no matching prediction is a false negative (FN).
- Precision = TP / (TP + FP); Recall = TP / (TP + FN); F1 = 2PR / (P + R).
- AP = area under the precision-recall curve (101-point interpolation, COCO style).
- mAP@0.5 = mean AP over classes at IoU 0.5; mAP@0.5:0.95 = mean over IoU 0.50…0.95.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

IOU_THRESHOLDS = np.round(np.linspace(0.5, 0.95, 10), 2)


@dataclass
class ImageBoxes:
    boxes: np.ndarray                 # (n, 4) xyxy pixels
    classes: np.ndarray               # (n,) int
    scores: np.ndarray | None = None  # (n,) float for predictions
    image_id: str = ""
    meta: dict = field(default_factory=dict)

    @classmethod
    def empty(cls, image_id: str = "", with_scores: bool = False) -> "ImageBoxes":
        return cls(np.zeros((0, 4)), np.zeros(0, dtype=int), np.zeros(0) if with_scores else None, image_id)


def box_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)))
    top_left = np.maximum(a[:, None, :2], b[None, :, :2])
    bottom_right = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(bottom_right - top_left, 0, None)
    intersection = wh[..., 0] * wh[..., 1]
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return intersection / np.clip(area_a[:, None] + area_b[None, :] - intersection, 1e-9, None)


def match_same_class(gt: ImageBoxes, pred: ImageBoxes, iou_threshold: float) -> np.ndarray:
    """Greedy matching by descending score. Returns a bool TP flag per prediction."""
    tp = np.zeros(len(pred.classes), dtype=bool)
    if len(pred.classes) == 0 or len(gt.classes) == 0:
        return tp
    ious = box_iou(pred.boxes, gt.boxes)
    used = np.zeros(len(gt.classes), dtype=bool)
    for index in np.argsort(-pred.scores, kind="stable"):
        candidates = (gt.classes == pred.classes[index]) & ~used
        if not candidates.any():
            continue
        overlaps = np.where(candidates, ious[index], -1)
        best = int(overlaps.argmax())
        if overlaps[best] >= iou_threshold:
            tp[index] = True
            used[best] = True
    return tp


def average_precision(recall: np.ndarray, precision: np.ndarray) -> float:
    """101-point interpolated AP exactly as pycocotools computes it.

    Inputs are cumulative recall/precision in descending-score order. Precision is first
    made monotonically decreasing (the 'envelope'); then for each recall level
    r in {0, 0.01, ..., 1} we take the precision at the first point with recall >= r
    (0 if that recall is never reached) and average the 101 values.
    """
    if recall.size == 0:
        return 0.0
    envelope = np.flip(np.maximum.accumulate(np.flip(precision)))
    points = np.linspace(0, 1, 101)
    indexes = np.searchsorted(recall, points, side="left")
    sampled = np.where(indexes < len(envelope), envelope[np.minimum(indexes, len(envelope) - 1)], 0.0)
    return float(sampled.mean())


@dataclass
class ClassCurves:
    ap: np.ndarray            # (len(IOU_THRESHOLDS),)
    precision_at: np.ndarray  # precision as a function of confidence grid
    recall_at: np.ndarray     # recall as a function of confidence grid
    pr_recall: np.ndarray     # PR curve x (IoU 0.5)
    pr_precision: np.ndarray  # PR curve y (IoU 0.5)
    n_gt: int


def evaluate(gts: list[ImageBoxes], preds: list[ImageBoxes], class_names: list[str],
             conf_grid: np.ndarray | None = None) -> dict:
    """Compute AP per class/IoU and confidence curves. gts and preds are aligned lists."""
    assert len(gts) == len(preds), "gts and preds must be aligned per image"
    conf_grid = np.linspace(0, 1, 1000) if conf_grid is None else conf_grid
    n_classes = len(class_names)
    # tp flags per IoU threshold for every prediction, concatenated over images
    all_scores, all_classes, all_tp = [], [], []
    for gt, pred in zip(gts, preds):
        if len(pred.classes) == 0:
            continue
        all_scores.append(pred.scores)
        all_classes.append(pred.classes)
        all_tp.append(np.stack([match_same_class(gt, pred, thr) for thr in IOU_THRESHOLDS], axis=1))
    scores = np.concatenate(all_scores) if all_scores else np.zeros(0)
    classes = np.concatenate(all_classes) if all_classes else np.zeros(0, dtype=int)
    tps = np.concatenate(all_tp) if all_tp else np.zeros((0, len(IOU_THRESHOLDS)), dtype=bool)
    gt_counts = np.bincount(np.concatenate([g.classes for g in gts]).astype(int) if gts else np.zeros(0, int),
                            minlength=n_classes)[:n_classes]

    curves: dict[int, ClassCurves] = {}
    for class_id in range(n_classes):
        mask = classes == class_id
        order = np.argsort(-scores[mask], kind="stable")
        class_scores = scores[mask][order]
        class_tp = tps[mask][order]
        n_gt = int(gt_counts[class_id])
        ap = np.zeros(len(IOU_THRESHOLDS))
        precision_at = np.zeros_like(conf_grid)
        recall_at = np.zeros_like(conf_grid)
        pr_recall = pr_precision = np.zeros(0)
        if n_gt > 0 and len(class_scores):
            cum_tp = np.cumsum(class_tp, axis=0)
            cum_fp = np.cumsum(~class_tp, axis=0)
            recall = cum_tp / n_gt
            precision = cum_tp / np.maximum(cum_tp + cum_fp, 1e-9)
            ap = np.array([average_precision(recall[:, k], precision[:, k]) for k in range(len(IOU_THRESHOLDS))])
            # Curves vs confidence (IoU 0.5); scores are descending so negate for np.interp.
            recall_at = np.interp(-conf_grid, -class_scores, recall[:, 0], left=0)
            precision_at = np.interp(-conf_grid, -class_scores, precision[:, 0], left=1)
            pr_recall, pr_precision = recall[:, 0], precision[:, 0]
        curves[class_id] = ClassCurves(ap, precision_at, recall_at, pr_recall, pr_precision, n_gt)

    present = [cid for cid in range(n_classes) if curves[cid].n_gt > 0]
    f1_at = {cid: 2 * curves[cid].precision_at * curves[cid].recall_at /
             np.maximum(curves[cid].precision_at + curves[cid].recall_at, 1e-9) for cid in present}
    # Pooled (all-class) F1 vs confidence: the same TP/FP/FN counting as the reported
    # precision/recall, so the chosen threshold maximises the F1 we actually report.
    total_gt = int(gt_counts.sum())
    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    cum_tp = np.cumsum(tps[order, 0]) if len(order) else np.zeros(0)
    kept = np.searchsorted(-sorted_scores, -conf_grid, side="right")   # predictions with score >= conf
    tp_at = np.where(kept > 0, cum_tp[np.maximum(kept - 1, 0)] if len(cum_tp) else 0, 0)
    precision_pooled = np.where(kept > 0, tp_at / np.maximum(kept, 1), 1.0)
    recall_pooled = tp_at / max(total_gt, 1)
    mean_f1 = 2 * precision_pooled * recall_pooled / np.maximum(precision_pooled + recall_pooled, 1e-9)
    best_index = int(mean_f1.argmax()) if present else 0

    per_class = {}
    for class_id, name in enumerate(class_names):
        c = curves[class_id]
        per_class[name] = {
            "instances": c.n_gt,
            "ap50": round(float(c.ap[0]), 4),
            "ap50_95": round(float(c.ap.mean()), 4),
            "precision_at_operating": round(float(c.precision_at[best_index]), 4) if c.n_gt else None,
            "recall_at_operating": round(float(c.recall_at[best_index]), 4) if c.n_gt else None,
        }
    return {
        "map50": round(float(np.mean([curves[c].ap[0] for c in present])) if present else 0.0, 4),
        "map50_95": round(float(np.mean([curves[c].ap.mean() for c in present])) if present else 0.0, 4),
        "per_class": per_class,
        # Rounded *up* so applying the stored threshold keeps exactly the chosen predictions.
        "operating_confidence": float(np.ceil(conf_grid[best_index] * 1000) / 1000),
        "operating_f1": round(float(mean_f1[best_index]), 4),
        "_curves": {"conf_grid": conf_grid, "curves": curves, "mean_f1": mean_f1, "f1_at": f1_at},
    }


def confusion_and_errors(gts: list[ImageBoxes], preds: list[ImageBoxes], n_classes: int,
                         conf: float, iou_threshold: float = 0.5) -> dict:
    """Class-agnostic matching at the operating threshold.

    Returns a confusion matrix with rows = true class and columns = predicted class,
    where index n_classes is 'background' (missed object / false alarm), plus
    TP/FP/FN per class and per-image error records for the gallery.
    """
    bg = n_classes
    matrix = np.zeros((n_classes + 1, n_classes + 1), dtype=int)
    errors: list[dict] = []
    for gt, pred in zip(gts, preds):
        keep = pred.scores >= conf if pred.scores is not None else np.ones(len(pred.classes), bool)
        p_boxes, p_classes, p_scores = pred.boxes[keep], pred.classes[keep], pred.scores[keep]
        ious = box_iou(gt.boxes, p_boxes)
        used_gt = np.zeros(len(gt.classes), bool)
        used_pred = np.zeros(len(p_classes), bool)
        if ious.size:
            for flat in np.argsort(-ious, axis=None):
                gi, pi = np.unravel_index(flat, ious.shape)
                if ious[gi, pi] < iou_threshold:
                    break
                if used_gt[gi] or used_pred[pi]:
                    continue
                used_gt[gi] = used_pred[pi] = True
                matrix[gt.classes[gi], p_classes[pi]] += 1
                if gt.classes[gi] != p_classes[pi]:
                    errors.append({"kind": "misclassified", "image_id": gt.image_id, "box": p_boxes[pi].tolist(),
                                   "true_class": int(gt.classes[gi]), "pred_class": int(p_classes[pi]),
                                   "score": float(p_scores[pi]), "meta": gt.meta})
        for gi in np.where(~used_gt)[0]:
            matrix[gt.classes[gi], bg] += 1
            errors.append({"kind": "false_negative", "image_id": gt.image_id, "box": gt.boxes[gi].tolist(),
                           "true_class": int(gt.classes[gi]), "meta": gt.meta})
        for pi in np.where(~used_pred)[0]:
            matrix[bg, p_classes[pi]] += 1
            errors.append({"kind": "false_positive", "image_id": gt.image_id, "box": p_boxes[pi].tolist(),
                           "pred_class": int(p_classes[pi]), "score": float(p_scores[pi]), "meta": gt.meta})

    counts = {}
    for class_id in range(n_classes):
        tp = int(matrix[class_id, class_id])
        fn = int(matrix[class_id, :].sum() - tp)
        fp = int(matrix[:, class_id].sum() - tp)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        counts[class_id] = {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4),
                            "recall": round(recall, 4), "f1": round(f1, 4)}
    total_tp = sum(c["tp"] for c in counts.values())
    total_fp = sum(c["fp"] for c in counts.values())
    total_fn = sum(c["fn"] for c in counts.values())
    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    return {
        "matrix": matrix,
        "per_class": counts,
        "overall": {
            "tp": total_tp, "fp": total_fp, "fn": total_fn,
            "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
        },
        "errors": errors,
    }


def size_bucket(box: list[float] | np.ndarray, image_area: float) -> str:
    """COCO-like relative size buckets (fraction of image area)."""
    area = max(0.0, (box[2] - box[0]) * (box[3] - box[1])) / max(image_area, 1.0)
    return "small" if area < 0.005 else "medium" if area < 0.05 else "large"
