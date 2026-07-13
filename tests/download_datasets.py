r"""Download high-quality SO101 community datasets
Usage:
    C:\Users\XU\.conda\envs\lerobot06\python.exe tests\download_datasets.py
"""

import os
import json
from huggingface_hub import snapshot_download, hf_hub_download

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets")

# Top 3 quality SO101 datasets
DATASETS = [
    {
        "name": "lerobot/svla_so101_pickplace",
        "task": "pick-place (official)",
        "episodes": 50,
        "why": "HuggingFace official, highest downloads (2383), best quality benchmark",
    },
    {
        "name": "lerobotForScienceEdu/so101_stacking",
        "task": "stacking",
        "episodes": 50,
        "why": "Different task from pick-place, good for multi-skill training",
    },
    {
        "name": "fl-ymd/so101_pickplace_block_1_lerobot_v2.1",
        "task": "pick-place (block, 50fps)",
        "episodes": 50,
        "why": "50 parquet files, v2.1 format, standard block pick-and-place",
    },
]


def download_one(ds):
    ds_name = ds["name"]
    local = os.path.join(DATASET_DIR, ds_name.replace("/", "__"))
    print(f"\n{'='*55}")
    print(f"  {ds_name}")
    print(f"  task: {ds['task']}, episodes: {ds['episodes']}")
    print(f"  reason: {ds['why']}")

    if os.path.exists(os.path.join(local, "meta/info.json")):
        # already downloaded
        with open(os.path.join(local, "meta/info.json")) as f:
            info = json.load(f)
        print(f"  ALREADY downloaded: {info.get('total_episodes', '?')} episodes")
        return

    try:
        # Download meta first to confirm
        meta_path = hf_hub_download(
            ds_name, "meta/info.json", repo_type="dataset",
            local_dir=local, local_dir_use_symlinks=False
        )
        with open(meta_path) as f:
            info = json.load(f)
        print(f"  Meta: robot={info.get('robot_type')},"
              f" eps={info.get('total_episodes')},"
              f" frames={info.get('total_frames', '?')},"
              f" fps={info.get('fps', '?')}")

        # Full download (skip videos for speed; re-download later if needed)
        ignore_patterns = ["videos/**"] if ds["episodes"] > 20 else []
        print(f"  Downloading data files (ignoring videos={bool(ignore_patterns)})...")
        local_dir = snapshot_download(
            ds_name, repo_type="dataset",
            local_dir=local, local_dir_use_symlinks=False,
            ignore_patterns=ignore_patterns,
            resume_download=True,
        )
        # Count downloaded parquet files
        count = sum(1 for root, _, files in os.walk(local_dir)
                    for f in files if f.endswith('.parquet'))
        size = sum(os.path.getsize(os.path.join(root, f))
                   for root, _, files in os.walk(local_dir)
                   for f in files)
        print(f"  DONE: {count} parquet files, {size/1024/1024:.1f} MB")
    except Exception as e:
        print(f"  FAILED: {e}")


if __name__ == "__main__":
    os.makedirs(DATASET_DIR, exist_ok=True)
    print("SO101 Dataset Downloader")
    print(f"Target: {os.path.abspath(DATASET_DIR)}")
    for ds in DATASETS:
        download_one(ds)
    print(f"\nAll done. Data in: {os.path.abspath(DATASET_DIR)}")
