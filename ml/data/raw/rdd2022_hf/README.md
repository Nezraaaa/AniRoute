---
language:
- en
license: cc-by-sa-4.0
pretty_name: RDD2022 Multi-National Road Damage Detection Dataset (4-Class YOLO Export)
task_categories:
- object-detection
tags:
- object-detection
- road-damage
- pavement-distress
- infrastructure
- autonomous-driving
- crowdsensing
- computer-vision
- ultralytics
- yolo
size_categories:
- 10K<n<100K
configs:
- config_name: default
  data_files:
  - split: train
    path:
    - data/images/train/shard_000/*.jpg
    - data/images/train/shard_001/*.jpg
    - data/images/train/shard_002/*.jpg
    - data/images/train/shard_003/*.jpg
    - data/images/train/shard_004/*.jpg
    - data/images/train/shard_005/*.jpg
    - data/images/train/shard_006/*.jpg
    - data/images/train/shard_007/*.jpg
    - data/images/train/shard_008/*.jpg
    - data/images/train/shard_000/metadata.jsonl
    - data/images/train/shard_001/metadata.jsonl
    - data/images/train/shard_002/metadata.jsonl
    - data/images/train/shard_003/metadata.jsonl
    - data/images/train/shard_004/metadata.jsonl
    - data/images/train/shard_005/metadata.jsonl
    - data/images/train/shard_006/metadata.jsonl
    - data/images/train/shard_007/metadata.jsonl
    - data/images/train/shard_008/metadata.jsonl
  - split: validation
    path:
    - data/images/valid/shard_000/*.jpg
    - data/images/valid/shard_001/*.jpg
    - data/images/valid/shard_000/metadata.jsonl
    - data/images/valid/shard_001/metadata.jsonl
  - split: test
    path:
    - data/images/test/shard_000/*.jpg
    - data/images/test/shard_001/*.jpg
    - data/images/test/shard_000/metadata.jsonl
    - data/images/test/shard_001/metadata.jsonl
---

<h1 align="center">RDD2022: Multi-National Road Damage Detection Dataset (4-Class YOLO Export)</h1>

<p align="center">
  <img src="rdd2022_banner.jpg" alt="RDD2022 Dataset Banner"/>
</p>

![Task](https://img.shields.io/badge/Task-Object%20Detection-blue?style=flat-square)
![Dataset](https://img.shields.io/badge/Dataset-RDD2022-0aa1a7?style=flat-square)
![Format](https://img.shields.io/badge/Format-YOLO%20Compatible-orange?style=flat-square)
![Classes](https://img.shields.io/badge/Classes-4-success?style=flat-square)
![Splits](https://img.shields.io/badge/Splits-Train%20%7C%20Val%20%7C%20Test-blueviolet?style=flat-square)
![License](https://img.shields.io/badge/License-CC%20BY--SA%204.0-lightgrey?style=flat-square)

> **Unofficial redistribution of the RDD2022 multi-national road-damage dataset, reduced to the 4-class CRDDC2022 taxonomy and reformatted into a standardized YOLO-compatible directory layout, under the original CC BY-SA 4.0 license.**

## Dataset Description

- **Homepage:** https://github.com/sekilab/RoadDamageDetector
- **Repository:** https://github.com/sekilab/RoadDamageDetector
- **Paper:** https://arxiv.org/abs/2209.08538
- **Leaderboard:** https://crddc2022.sekilab.global/leaderboard/

## Disclaimer

This repository is **not** an official release of the RDD2022 dataset.

RDD2022 was created by Deeksha Arya, Hiroya Maeda, Sanjay Kumar Ghosh, Durga Toshniwal, and Yoshihide Sekimoto (University of Tokyo and collaborators), and released as part of the **Crowdsensing-based Road Damage Detection Challenge (CRDDC'2022)**. The original authors and contributing institutions retain all copyright and intellectual property rights. This repository does **not** claim ownership of any images, annotations, or metadata.

This repository exists for two purposes:

1. To reorganize the dataset into a standardized YOLO/Ultralytics-compatible directory structure, with the six national subsets merged into a single train/val/test split.
2. To provide a more reliable download source for the 4-class subset used by most road-damage detection benchmarks.

**Two-hop provenance.** The RDD2022 official release ships per-country **Pascal-VOC XML** annotations. This repository is built from a YOLO-format conversion of that release (the `RDD_SPLIT` export) — which merged the national subsets and re-split the publicly-labelled images into train/val/test — followed by the 4-class reduction described below. The original authors are credited below; **cite the RDD2022 paper, not this repository.**

---

# Dataset Overview

RDD2022 is a multi-national street-level road-damage detection benchmark: **47,420 road images from six countries** (Japan, India, the Czech Republic, Norway, the United States, and China), captured with vehicle-mounted smartphones, dashboard cameras, and drones, and annotated for pavement distress. It was assembled to benchmark automatic road-condition assessment across diverse road types, imaging setups, and damage conventions.

This export covers the **publicly-labelled portion** of RDD2022 (38,385 images — the official `train` release), merged across all six countries and re-split into train/val/test. It keeps the four damage types scored by the CRDDC2022 challenge:

| code | class name (here)     | description                     |
|------|-----------------------|---------------------------------|
| D00  | `longitudinal_crack`  | longitudinal (wheel-path) crack |
| D10  | `transverse_crack`    | transverse (lateral) crack      |
| D20  | `alligator_crack`     | alligator / fatigue crack       |
| D40  | `pothole`             | pothole                         |

**No public test-set labels.** RDD2022's official challenge test set (~9,035 images) has no released annotations — it is held out for the CRDDC2022 evaluation server. It is **not** included here; the `test` split below is a held-out slice of the publicly-labelled images.

---

# Changes from the Official Release

### 1. RDD2022 Pascal-VOC release &rarr; YOLO conversion (`RDD_SPLIT`)

The original per-country `.xml` annotations were converted to normalized YOLO `.txt` labels, the six national subsets were merged, and the publicly-labelled images were split **70 / 15 / 15** into train / val / test (26,869 / 5,758 / 5,758 images). Boxes were re-expressed, not resized or moved.

### 2. `RDD_SPLIT` &rarr; this repository

- **Reduced to 4 classes.** The YOLO conversion above carries a 5th class id (`4`) — an "other" / D50-style bucket covering block cracks, road repairs, and country-specific damage codes that the CRDDC2022 challenge does **not** score. All class-4 boxes (**~6,545 total: 4,628 train / 965 valid / 951 test**) are **dropped**, leaving the four-class CRDDC2022 taxonomy (D00 / D10 / D20 / D40). Images whose boxes were all class 4 are kept as background frames.
- A handful of degenerate zero-area boxes were additionally skipped during conversion (fewer than 5 per split).
- **Format normalized** into a canonical COCO JSON per split plus the YOLO `.txt` labels above.
- No image pixel content was modified. No splits were changed relative to `RDD_SPLIT`.
- Roughly one third of images have no in-taxonomy damage and are kept with an empty label file — consistent with the source data (clean-road frames).

---

# Dataset Structure

```text
<repo>/
├── README.md
├── rdd2022_banner.jpg
└── data/
    ├── data.yaml
    ├── images/
    │   ├── train/  shard_000 … shard_008/   (26,869 *.jpg, ~3,000 per shard)
    │   ├── valid/  shard_000 … shard_001/   (5,758 *.jpg)
    │   └── test/   shard_000 … shard_001/   (5,758 *.jpg)
    └── labels/
        ├── train/  shard_000 … shard_008/   (*.txt, mirrors images)
        ├── valid/  shard_000 … shard_001/
        └── test/   shard_000 … shard_001/
```

where:

* `data/images/<split>/shard_NNN/` contains the street-level RGB road images. Filenames are prefixed by country of origin (e.g. `Japan_######.jpg`, `India_######.jpg`, `United_States_######.jpg`). Images are split into `shard_NNN/` subdirectories of ~3,000 files to stay within Hugging Face's 10,000-files-per-directory limit.
* `data/labels/<split>/shard_NNN/` contains one YOLO-format `.txt` per image (`class x_center y_center width height`, normalized; empty for images with no in-taxonomy damage), mirroring the image shard layout.
* `data/data.yaml` is the Ultralytics dataset configuration file (class names, split paths, relative to `data/`). Ultralytics resolves the shards automatically — it globs images recursively and derives each label path by swapping `/images/` &rarr; `/labels/`.
* Splits: **train** 26,869 images / 41,667 boxes &middot; **valid** 5,758 images / 8,776 boxes &middot; **test** 5,758 images / 8,724 boxes (38,385 images / 59,167 boxes total).

### Classes (4)

| id | class name           | code | train boxes |
|----|----------------------|------|-------------|
| 0  | `longitudinal_crack` | D00  | 18,201      |
| 1  | `transverse_crack`   | D10  | 8,386       |
| 2  | `alligator_crack`    | D20  | 7,526       |
| 3  | `pothole`            | D40  | 7,554       |

`longitudinal_crack` accounts for roughly 44% of training boxes. Country and imaging-setup distribution is uneven (Japan and India contribute the most images); performance can vary substantially by country of origin.

---

# Dataset Sources

## Original Paper

**RDD2022: A multi-national image dataset for automatic Road Damage Detection**

Deeksha Arya, Hiroya Maeda, Sanjay Kumar Ghosh, Durga Toshniwal, Yoshihide Sekimoto

arXiv:2209.08538, 2022. Released with the Crowdsensing-based Road Damage Detection Challenge (CRDDC'2022).

Preceded by the RDD2020 release (Arya et al., *Data in Brief*, 2021) and earlier RDD2018/2019 work.

## Official Resources

- **Official Repository:** https://github.com/sekilab/RoadDamageDetector
- **arXiv:** https://arxiv.org/abs/2209.08538
- **Dataset Ninja catalogue:** https://datasetninja.com/road-damage-detector

---

# Attribution

**All credit for collecting and annotating this dataset belongs entirely to the original RDD2022 authors: Deeksha Arya, Hiroya Maeda, Sanjay Kumar Ghosh, Durga Toshniwal, and Yoshihide Sekimoto**, and the contributing institutions of the six national subsets.

This repository only converts their data to a YOLO layout, merges the national subsets, and reduces the label set to the 4-class CRDDC2022 taxonomy, for improved usability. It does not modify, reinterpret, or take credit for the underlying imagery or annotations.

If you use this dataset in your research, **please cite the original publication below.**

---

# License

The RDD2022 images are released by their creators under the **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)** license, as stated in the [official repository](https://github.com/sekilab/RoadDamageDetector) and the RDD2022 paper.

Accordingly:

- Attribution to the original authors is required.
- Commercial and non-commercial use are both permitted.
- **Share-alike:** any redistribution or derivative work — **including this export and anything built from it** — must be distributed under CC BY-SA 4.0.

This repository is distributed under the same **CC BY-SA 4.0** license.

---

# Citation

If you use this dataset, please cite:

```bibtex
@article{arya2022rdd2022,
  title = {RDD2022: A multi-national image dataset for automatic Road Damage Detection},
  author = {Arya, Deeksha and Maeda, Hiroya and Ghosh, Sanjay Kumar and Toshniwal, Durga and Sekimoto, Yoshihide},
  journal = {arXiv preprint arXiv:2209.08538},
  year = {2022}
}
```

---

# Acknowledgements

We sincerely thank Deeksha Arya, Hiroya Maeda, Sanjay Kumar Ghosh, Durga Toshniwal, Yoshihide Sekimoto, and all the contributing institutions of the six national subsets for assembling, annotating, and publicly releasing this valuable multi-national road-infrastructure benchmark, and the organizers of the CRDDC'2022 challenge.
