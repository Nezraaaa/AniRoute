import numpy as np
import pytest

from ml.evaluation.metrics import ImageBoxes, average_precision, box_iou, confusion_and_errors, evaluate, size_bucket


def gt(boxes, classes, image_id="img"):
    return ImageBoxes(np.array(boxes, float).reshape(-1, 4), np.array(classes, int), None, image_id,
                      {"width": 100, "height": 100, "luma": 120, "path": ""})


def pred(boxes, classes, scores, image_id="img"):
    return ImageBoxes(np.array(boxes, float).reshape(-1, 4), np.array(classes, int), np.array(scores, float), image_id)


def test_box_iou():
    a = np.array([[0, 0, 10, 10]], float)
    b = np.array([[0, 0, 10, 10], [5, 0, 15, 10], [20, 20, 30, 30]], float)
    np.testing.assert_allclose(box_iou(a, b), [[1.0, 1 / 3, 0.0]])


def test_perfect_predictions_give_map_one():
    gts = [gt([[10, 10, 50, 50], [60, 60, 90, 90]], [0, 1])]
    preds = [pred([[10, 10, 50, 50], [60, 60, 90, 90]], [0, 1], [0.9, 0.8])]
    result = evaluate(gts, preds, ["pothole", "severe_road_damage"])
    assert result["map50"] == pytest.approx(1.0)
    assert result["map50_95"] == pytest.approx(1.0)


def test_false_positive_and_miss_lower_ap_and_show_in_confusion():
    gts = [gt([[10, 10, 50, 50], [60, 60, 90, 90]], [0, 0])]
    # one correct pothole, one false alarm, one pothole predicted as the wrong class
    preds = [pred([[10, 10, 50, 50], [0, 70, 5, 75], [60, 60, 90, 90]], [0, 0, 1], [0.9, 0.8, 0.7])]
    result = evaluate(gts, preds, ["pothole", "severe_road_damage"])
    assert 0 < result["map50"] < 1
    cm = confusion_and_errors(gts, preds, 2, conf=0.5)
    matrix = cm["matrix"]
    assert matrix[0, 0] == 1          # TP pothole
    assert matrix[0, 1] == 1          # pothole → severe_road_damage
    assert matrix[2, 0] == 1          # background → pothole (false alarm)
    assert cm["per_class"][0] == {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    kinds = sorted(e["kind"] for e in cm["errors"])
    assert kinds == ["false_positive", "misclassified"]


def test_threshold_filters_low_confidence_predictions():
    gts = [gt([[10, 10, 50, 50]], [0])]
    preds = [pred([[10, 10, 50, 50], [60, 60, 90, 90]], [0, 0], [0.9, 0.1])]
    assert confusion_and_errors(gts, preds, 1, conf=0.5)["overall"]["fp"] == 0
    assert confusion_and_errors(gts, preds, 1, conf=0.05)["overall"]["fp"] == 1


def test_operating_threshold_separates_true_and_false_scores():
    gts = [gt([[10, 10, 50, 50]], [0], f"i{i}") for i in range(10)]
    preds = [pred([[10, 10, 50, 50], [60, 60, 90, 90]], [0, 0], [0.8, 0.3], f"i{i}") for i in range(10)]
    result = evaluate(gts, preds, ["pothole"])
    assert 0.3 < result["operating_confidence"] <= 0.8
    assert result["operating_f1"] == pytest.approx(1.0, abs=1e-3)


def test_average_precision_edge_cases():
    assert average_precision(np.array([]), np.array([])) == 0.0
    assert average_precision(np.array([1.0]), np.array([1.0])) == pytest.approx(1.0)
    # Half the objects found with perfect precision → recall levels 0.00…0.50 score 1 (51/101).
    assert average_precision(np.array([0.5]), np.array([1.0])) == pytest.approx(51 / 101)
    # A false positive ranked first is penalised by the precision envelope.
    assert average_precision(np.array([0.0, 1.0]), np.array([0.0, 0.5])) == pytest.approx(0.5)


def test_size_bucket():
    assert size_bucket([0, 0, 5, 5], 100 * 100) == "small"
    assert size_bucket([0, 0, 20, 20], 100 * 100) == "medium"
    assert size_bucket([0, 0, 60, 60], 100 * 100) == "large"
