r"""Download SO101 dataset videos for VLA training
Usage:
    C:\Users\XU\.conda\envs\lerobot06\python.exe tests\download_videos.py
"""

import os, json
from huggingface_hub import snapshot_download, list_repo_files

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "datasets")


def download_videos(ds_name):
    local = os.path.join(DATASET_DIR, ds_name.replace("/", "__"))

    # Check what video files exist
    files = list(list_repo_files(ds_name, repo_type='dataset'))
    video_files = [f for f in files if 'video' in f.lower() or f.endswith('.mp4')]
    print(f"  Videos on Hub: {len(video_files)} files")
    for vf in video_files[:5]:
        print(f"    {vf}")

    # Download only videos (data already exists)
    print(f"  Downloading videos...")
    snapshot_download(
        ds_name, repo_type="dataset",
        local_dir=local,
        resume_download=True,
        allow_patterns=["videos/**", "*.mp4", "*.webm"],
    )

    # Check result
    local_videos = []
    for root, _, fs in os.walk(local):
        for f in fs:
            if f.endswith(('.mp4', '.webm')) or 'video' in root.lower():
                local_videos.append(os.path.join(root, f))
    size = sum(os.path.getsize(v) for v in local_videos)
    print(f"  Done: {len(local_videos)} videos, {size/1024/1024:.1f} MB")
    return len(local_videos)


if __name__ == "__main__":
    datasets = [
        "lerobot/svla_so101_pickplace",
        "lerobotForScienceEdu/so101_stacking",
        "fl-ymd/so101_pickplace_block_1_lerobot_v2.1",
    ]
    print("SO101 Video Downloader\n")
    total = 0
    for ds in datasets:
        print(f"{ds}")
        total += download_videos(ds)
        print()
    print(f"All done. {total} video files downloaded.")
