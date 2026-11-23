"""Download a reproducible RDD2022 subset (YOLO format) from the public Hugging Face mirror.

  python ml/scripts/download_rdd2022.py --country India --train 1800 --valid 450 --test 450

Mirror: https://huggingface.co/datasets/dronefreak/RDD2022 (CC BY-SA 4.0), a YOLO-format copy of
RDD2022 (Arya et al., arXiv:2209.08538). Classes: 0 longitudinal_crack (D00), 1 transverse_crack
(D10), 2 alligator_crack (D20), 3 pothole (D40). The subset is a seeded random sample of each split,
so the same command always downloads the same images. No account is needed.
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATASET = "dronefreak/RDD2022"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--country", default="India")
    parser.add_argument("--train", type=int, default=1800)
    parser.add_argument("--valid", type=int, default=450)
    parser.add_argument("--test", type=int, default=450)
    parser.add_argument("--out", type=Path, default=REPO / "ml" / "data" / "raw" / "rdd2022_hf")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from huggingface_hub import HfApi, snapshot_download

    files = HfApi().list_repo_files(DATASET, repo_type="dataset")
    rng = random.Random(args.seed)
    patterns = ["data/data.yaml", "README.md"]
    for split, count in (("train", args.train), ("valid", args.valid), ("test", args.test)):
        images = sorted(f for f in files if f.startswith(f"data/images/{split}/")
                        and f.rsplit("/", 1)[-1].startswith(f"{args.country}_") and f.endswith(".jpg"))
        chosen = rng.sample(images, min(count, len(images)))
        for image in chosen:
            patterns.append(image)
            patterns.append(image.replace("data/images/", "data/labels/", 1).rsplit(".", 1)[0] + ".txt")
        print(f"{split}: {len(chosen)} of {len(images)} {args.country} images")
    snapshot_download(DATASET, repo_type="dataset", local_dir=str(args.out), allow_patterns=patterns, max_workers=16)
    print(f"saved to {args.out}")


if __name__ == "__main__":
    main()
