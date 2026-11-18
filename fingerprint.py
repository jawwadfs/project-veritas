"""
Module 1: Reconstruction Fingerprint Extraction
================================================
Core idea (matches the full diffusion-based method):
  Take an image → "reconstruct" it at several blur/noise strengths → measure
  how the residual (original − reconstructed) behaves at each strength.

  Real photos and AI-generated images react *differently* to this multi-strength
  reconstruction — the same differential reaction they show when passed through a
  diffusion denoiser at several noise levels ("diffusion snap-back").

  This lightweight proxy (box-blur instead of a full diffusion model) captures
  the same structural idea and runs on CPU with no model download.

  Production version: swap _box_blur() for a pretrained VAE encoder+decoder
  (e.g. Stable Diffusion's KL-VAE) and feed each image through it at noise
  strengths t ∈ {0.1, 0.3, 0.5, 0.7}.  The rest of the pipeline is identical.
"""

import numpy as np


def _box_blur(img: np.ndarray, k: int) -> np.ndarray:
    """
    Vectorised box-blur via integral image — O(H·W), no Python-level pixel loop.
    Analogous to a single forward+backward pass of a diffusion model at noise level k.
    """
    if k <= 1:
        return img
    H, W = img.shape
    padded = np.pad(img, k // 2, mode="reflect")[: H + k, : W + k]
    ii = np.pad(np.cumsum(np.cumsum(padded, axis=0), axis=1), ((1, 0), (1, 0)))
    s = (
        ii[k : k + H, k : k + W]
        - ii[0:H, k : k + W]
        - ii[k : k + H, 0:W]
        + ii[0:H, 0:W]
    )
    return s / (k * k)


def extract_fingerprint(img: np.ndarray, strengths=(2, 4, 8)) -> np.ndarray:
    """
    Extract the multi-strength reconstruction fingerprint from a 2D image array (H, W).
    """
    feats = []
    for k in strengths:
        recon = _box_blur(img, k)
        residual = img - recon
        feats.append(residual.mean())
        feats.append(residual.std())
        feats.append(np.mean(residual ** 2))                   # energy
        feats.append(np.percentile(np.abs(residual), 95))     # 95th percentile

    # Global frequency feature: fraction of energy in high-frequency bands
    f = np.fft.fft2(img)
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)
    H, W = img.shape
    cy, cx = H // 2, W // 2
    r = min(H, W) // 4
    low_energy = mag[cy - r : cy + r, cx - r : cx + r].sum()
    total_energy = mag.sum() + 1e-8
    feats.append(1.0 - (low_energy / total_energy))

    return np.array(feats, dtype=np.float32)


def extract_native_forensics(pil_img):
    """
    Forensic analysis for arbitrary resolution camera / uploaded images.
    Preserves physical camera sensor noise (PRNU), checks camera hardware metadata,
    and scales to standard forensic resolution to prevent resolution artifacts.
    """
    from PIL import Image
    from scipy.ndimage import median_filter
    
    rgb = pil_img.convert('RGB')
    w, h = rgb.size
    
    # Check authentic camera hardware metadata
    exif = pil_img.getexif()
    has_cam_exif = any(k in exif for k in [271, 272]) # Make, Model
    cam_name = f"{exif.get(271, '')} {exif.get(272, '')}".strip()
    
    # Scale to standard forensic analysis resolution (1024 max dimension)
    # This prevents 4K/8K images from having microscopic filter kernels
    if max(w, h) > 512:
        scale = 1024.0 / max(w, h)
        norm_img = rgb.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    else:
        norm_img = rgb

    gray_norm = np.array(norm_img.convert('L'), dtype=np.float32) / 255.0
    
    # 1. Native sensor noise (high-pass residual)
    denoised = median_filter(gray_norm, size=3)
    noise_residual = gray_norm - denoised
    sensor_noise_var = float(np.var(noise_residual))
    
    # 2. Multi-patch fingerprint extraction
    patch_size = 64
    patches_fp = []
    w_n, h_n = norm_img.size
    coords = [
        (w_n // 2, h_n // 2),
        (w_n // 3, h_n // 3),
        (2 * w_n // 3, h_n // 3),
        (w_n // 3, 2 * h_n // 3),
        (2 * w_n // 3, 2 * h_n // 3),
    ]
    for px, py in coords:
        box = (max(0, px - patch_size // 2), max(0, py - patch_size // 2),
               min(w_n, px + patch_size // 2), min(h_n, py + patch_size // 2))
        patch = gray_norm[box[1]:box[3], box[0]:box[2]]
        if patch.shape == (patch_size, patch_size):
            patches_fp.append(extract_fingerprint(patch))
            
    if not patches_fp:
        resized = np.array(norm_img.convert('L').resize((64, 64), Image.LANCZOS), dtype=np.float32) / 255.0
        patches_fp = [extract_fingerprint(resized)]
        
    mean_fp = np.mean(patches_fp, axis=0)
    
    # 3. Frequency domain ratio
    f = np.fft.fft2(gray_norm)
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)
    cy, cx = h_n // 2, w_n // 2
    r_max = min(cy, cx) // 2
    y, x = np.ogrid[-cy:h_n-cy, -cx:w_n-cx]
    dist = np.sqrt(x*x + y*y)
    hf_ratio = float(mag[dist > (r_max * 0.75)].mean() / (mag[dist < (r_max * 0.15)].mean() + 1e-6))
    
    # Physical camera detection:
    # Authenticated if camera hardware EXIF is present OR sensor noise matches physical CMOS
    is_camera = has_cam_exif or (sensor_noise_var > 0.0006 and max(w, h) > 300)
    
    return {
        'mean_fingerprint': mean_fp,
        'sensor_noise_var': sensor_noise_var,
        'hf_ratio': hf_ratio,
        'noise_map': noise_residual,
        'is_camera': is_camera,
        'has_cam_exif': has_cam_exif,
        'cam_name': cam_name,
        'original_size': (w, h)
    }


def extract_batch(images: np.ndarray) -> np.ndarray:
    """Extract fingerprints for a batch of images."""
    return np.array([extract_fingerprint(img) for img in images])


def get_fingerprint_components(img: np.ndarray, strengths=(2, 4, 8)):
    """
    Returns the residual images at each strength (for visualization).
    Used by the demo app to show *what the fingerprint looks like*.
    """
    residuals = {}
    for k in strengths:
        recon = _box_blur(img, k)
        residuals[f"strength={k}"] = {
            "reconstructed": recon,
            "residual": img - recon,
        }
    return residuals
