"""
Dataset Downloader — CIFAKE
============================
Downloads a small subset of the CIFAKE dataset from HuggingFace.
CIFAKE contains:
  - REAL: 60,000 images from CIFAR-10 (real photos, 32×32)
  - FAKE: 60,000 AI-generated counterparts (Stable Diffusion v1.4)

We only grab a small subset (200 real + 200 fake) for the demo.
Saves to: data/real/ and data/fake/

Usage:
    python3 download_data.py
"""

import os
import sys
import numpy as np
from PIL import Image

SAVE_DIR = os.path.join(os.path.dirname(__file__), "data")
REAL_DIR = os.path.join(SAVE_DIR, "real")
FAKE_DIR = os.path.join(SAVE_DIR, "fake")
N_SAMPLES = 200   # per class — small enough to download fast

def already_downloaded():
    real_count = len([f for f in os.listdir(REAL_DIR) if f.endswith(".png")]) if os.path.exists(REAL_DIR) else 0
    fake_count = len([f for f in os.listdir(FAKE_DIR) if f.endswith(".png")]) if os.path.exists(FAKE_DIR) else 0
    return real_count >= N_SAMPLES and fake_count >= N_SAMPLES

def download():
    if already_downloaded():
        real_count = len(os.listdir(REAL_DIR))
        fake_count = len(os.listdir(FAKE_DIR))
        print(f"✅  Dataset already present — {real_count} real, {fake_count} fake images.")
        return True

    os.makedirs(REAL_DIR, exist_ok=True)
    os.makedirs(FAKE_DIR, exist_ok=True)

    try:
        from datasets import load_dataset
    except ImportError:
        print("❌  'datasets' package not installed. Run:  pip3 install datasets")
        return False

    print("⬇️  Downloading CIFAKE subset from HuggingFace...")
    print("    (This takes ~1-2 min on first run, then it's cached)")

    # Try multiple known dataset IDs in order
    dataset_ids = [
        ("dragonintelligence/CIFAKE-image-dataset", "test"),
        ("dragonintelligence/CIFAKE-image-dataset", "train"),
        ("yanbax/CIFAKE_autotrain_compatible", "train"),
    ]
    ds = None
    for ds_id, split in dataset_ids:
        try:
            print(f"  Trying: {ds_id} ({split})…")
            ds = load_dataset(ds_id, split=split, streaming=True)
            print(f"  ✅ Connected to {ds_id}")
            break
        except Exception as e:
            print(f"  ⚠️  {ds_id}: {e}")
            continue
    if ds is None:
        print("❌  Could not load any CIFAKE variant from HuggingFace.")
        return False

    real_saved = fake_saved = 0
    for item in ds:
        if real_saved >= N_SAMPLES and fake_saved >= N_SAMPLES:
            break
        # Handle different label field names across dataset variants
        label = item.get("label", item.get("labels", item.get("Label", 0)))
        img   = item.get("image", item.get("img", item.get("Image")))
        if img is None:
            continue
        if not isinstance(img, Image.Image):
            img = Image.fromarray(img)
        # Resize to 64×64 (our standard size)
        img = img.resize((64, 64), Image.LANCZOS).convert("L")  # grayscale
        if label == 0 and real_saved < N_SAMPLES:   # 0 = REAL in CIFAKE
            img.save(os.path.join(REAL_DIR, f"real_{real_saved:04d}.png"))
            real_saved += 1
        elif label == 1 and fake_saved < N_SAMPLES:  # 1 = FAKE
            img.save(os.path.join(FAKE_DIR, f"fake_{fake_saved:04d}.png"))
            fake_saved += 1
        if (real_saved + fake_saved) % 50 == 0 and (real_saved + fake_saved) > 0:
            print(f"  Saved: {real_saved} real, {fake_saved} fake…")

    print(f"✅  Done — {real_saved} real images → data/real/")
    print(f"           {fake_saved} fake images → data/fake/")
    return real_saved > 0 and fake_saved > 0


def load_images_as_arrays(n_real=50, n_fake=50, seed=0):
    """
    Load saved images as numpy arrays.
    Returns: images (N, 64, 64), labels (N,)  — 0=real, 1=fake
    """
    rng = np.random.default_rng(seed)

    def _load_dir(directory, label, n):
        files = sorted([f for f in os.listdir(directory) if f.endswith(".png")])
        chosen = rng.choice(files, size=min(n, len(files)), replace=False)
        arrays = []
        for fname in chosen:
            img = Image.open(os.path.join(directory, fname)).convert("L")
            arr = np.array(img, dtype=np.float32) / 255.0
            arrays.append(arr)
        return arrays, [label] * len(arrays)

    real_imgs, real_lbs = _load_dir(REAL_DIR, 0, n_real)
    fake_imgs, fake_lbs = _load_dir(FAKE_DIR, 1, n_fake)

    images = np.array(real_imgs + fake_imgs)
    labels = np.array(real_lbs + fake_lbs)
    idx = rng.permutation(len(labels))
    return images[idx], labels[idx]


def dataset_stats():
    """Return counts of saved images."""
    real = len(os.listdir(REAL_DIR)) if os.path.exists(REAL_DIR) else 0
    fake = len(os.listdir(FAKE_DIR)) if os.path.exists(FAKE_DIR) else 0
    return real, fake


if __name__ == "__main__":
    success = download()
    if success:
        print("\nDataset ready. Run  python3 main.py  or  streamlit run app.py")
    else:
        sys.exit(1)
