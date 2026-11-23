# System overview

## Architecture

```mermaid
flowchart LR
    subgraph Browser["Browser — Vue 3 web app"]
        CAM["Camera / recorded video / uploaded image"]
        SCAN["Frame scanner<br/>640 px JPEG every 0.6 s"]
        UI["Overlay boxes · alert · confirm dialog · map"]
    end
    subgraph API["FastAPI backend (laptop CPU)"]
        PRE["Preprocessing<br/>EXIF · letterbox 640 · CLAHE optional (off)"]
        A["Model A<br/>YOLO11 fine-tuned<br/>pothole · severe road damage"]
        B["Optional Model B (off)<br/>COCO-pretrained<br/>obstructions"]
        ROI["Driving-corridor rule<br/>(Model B only)"]
        MERGE["Merge → hazard types"]
        SMOOTH["Temporal smoothing<br/>2 of 3 frames · cooldown · dedupe"]
        STORE[("Confirmed observations<br/>JSONL + evidence JPEG")]
        RISK["Route risk<br/>hazards within 75 m × crop sensitivity"]
    end
    OSRM["OSRM routing<br/>(road geometry, ETA)"]

    CAM --> SCAN --> PRE
    PRE --> A --> MERGE
    PRE --> B --> ROI --> MERGE
    MERGE --> SMOOTH --> UI
    UI -- "driver confirms" --> STORE --> RISK
    OSRM --> RISK --> UI
```

## Detection flowchart (one camera frame)

```mermaid
flowchart TD
    F["Frame captured (browser)"] --> P["Preprocess:<br/>orientation fix<br/>letterbox to 640×640<br/>(CLAHE opt-in)"]
    P --> D["Run Model A and Model B on the same frame"]
    D --> T{"Confidence ≥ threshold?"}
    T -- no --> X["Discard box"]
    T -- yes --> R{"Model B box inside<br/>driving corridor and close?"}
    R -- no --> X
    R -- yes / Model A --> O["Draw box on live overlay"]
    O --> V{"Same hazard in ≥ 2 of<br/>last 3 frames?"}
    V -- no --> N["Keep scanning"]
    V -- yes --> C{"Cooldown passed and not a<br/>duplicate within 50 m?"}
    C -- no --> N
    C -- yes --> AL["Alert driver with annotated evidence frame"]
    AL --> Q{"Driver confirms?"}
    Q -- "not now" --> N
    Q -- confirm --> S["Save hazard + GPS + evidence"] --> RR["Re-score routes → recommend safer route if changed"]
```

## Components

| Layer | Files | Responsibility |
| --- | --- | --- |
| Preprocessing | `backend/vision/preprocess.py` | Decode, EXIF orientation, CLAHE, letterbox; shared with evaluation |
| Detectors | `backend/vision/detector.py` | Lazy YOLO loading; uses ONNX on Apple Silicon, otherwise OpenVINO → ONNX → PyTorch |
| Integration | `backend/vision/ensemble.py` | Runs Model A, the optional Model B, and the optional water-filled-pothole check (off by default); maps and merges results |
| Smoothing | `backend/vision/smoothing.py` | 2-of-3 voting, cooldown, 50 m dedupe |
| API | `backend/vision/router.py`, `backend/main.py` | `/api/vision/*`, `/api/model/*`, `/api/hazards/*`, `/api/routes/*` |
| Route risk | `backend/hazard_risk.py` | Point-to-route distance, severity weights, crop multiplier |
| Web app | `frontend/src/pages/*`, `components/vision/*` | Plan, Active Trip scanning, Evaluation, About |
| Training & evaluation | `ml/` | Dataset preparation, training presets, metrics, figures |

## API summary

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Status, whether detection is live, supported hazards |
| GET | `/api/model/info` | Models, thresholds, corridor, smoothing settings |
| GET | `/api/model/metrics` | Every report in `ml/reports/` (JSON + figure URLs) |
| POST | `/api/vision/detect` | Upload an image → boxes, annotated image, preprocessing stages |
| POST | `/api/vision/detect-frame` | Detect on a video/webcam frame (data URL) |
| POST | `/api/hazards/scanning/start` · `/stop` | Begin/end trip scanning (resets smoothing) |
| POST | `/api/hazards/scan-frame` | Trip frame → overlay boxes + smoothed alert + evidence |
| POST | `/api/hazards/confirm` | Save a confirmed hazard (GPS, confidence, evidence) |
| POST | `/api/routes/calculate` · `/recalculate` | OSRM routes scored with confirmed hazards |
| GET | `/api/samples`, `/samples/*`, `/reports/*` | Sample images, recorded drive and report figures |

## Data flow and privacy

Frames are processed in memory and discarded. Only the evidence frame of a hazard the driver confirms is
written to `backend/data/evidence/`, with its GPS position, in `backend/data/hazard_observations.jsonl`
(both git-ignored).
