"""
Module: Synthetic Data Generator
=================================
Stands in for real datasets (GenImage / SynthBuster / Artifact) while those are
being downloaded/curated.  Each "generator" gets its own distinct statistical
artifact signature, mimicking how different real AI image generators (Stable
Diffusion, DALL·E, Midjourney, Firefly, etc.) leave different frequency
fingerprints that a reconstruction-based method can expose.
"""

import numpy as np

IMG_SIZE = 64

# Generator names for display
GENERATOR_NAMES = [
    "StableDiffusion v1.5",
    "DALL·E 2",
    "Midjourney v5",
    "Firefly v2",
    "SDXL Turbo",
]

# Each generator gets a distinct frequency signature (widely spread so they are
# genuinely different — no shared noise term).
FREQ_TABLE = [0.15, 0.30, 0.55, 0.85, 1.30]


def _smooth_noise(seed, size=IMG_SIZE):
    """Simulate a 'real' photo texture: smooth, spatially correlated noise."""
    rng = np.random.default_rng(seed)
    low = rng.normal(0, 1, (size // 8, size // 8))
    up = np.kron(low, np.ones((8, 8)))  # simple nearest-neighbour upsample
    return up


def _generator_artifact(seed, generator_id, size=IMG_SIZE):
    """
    Simulate the AI-generator-specific fingerprint that diffusion
    reconstruction would reveal.  Each generator_id has a unique frequency
    and phase, making it genuinely distinct from every other generator.
    """
    rng = np.random.default_rng(seed + generator_id * 997)
    freq = FREQ_TABLE[generator_id % len(FREQ_TABLE)]
    phase = rng.uniform(0, 2 * np.pi)
    x = np.arange(size)
    y = np.arange(size)
    xx, yy = np.meshgrid(x, y)
    pattern = np.sin(freq * xx + phase) * np.cos(freq * yy + phase)
    return 0.8 * pattern


def make_dataset(generator_id, n_real, n_fake, seed=0):
    """
    Returns:
        images : np.ndarray of shape (n_real+n_fake, IMG_SIZE, IMG_SIZE)
        labels : np.ndarray of shape (n_real+n_fake,)  — 0=real, 1=AI-generated
    """
    images, labels = [], []

    for i in range(n_real):
        img = _smooth_noise(seed + i)
        images.append(img)
        labels.append(0)  # real

    for i in range(n_fake):
        base = _smooth_noise(seed + 10_000 + i)
        artifact = _generator_artifact(seed + i, generator_id)
        images.append(base + artifact)
        labels.append(1)  # AI-generated

    images = np.array(images)
    labels = np.array(labels)
    idx = np.random.default_rng(seed).permutation(len(labels))
    return images[idx], labels[idx]
