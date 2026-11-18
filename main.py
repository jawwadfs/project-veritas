"""
VERITAS — Main Experiment Runner
==================================
Simulates a sequential stream of 5 AI image generators arriving one at a time.
Compares three continual learning strategies and prints evaluation metrics.

Usage:
    python3 main.py

Output:
    - Console: per-stage accuracy breakdown + final metrics table
    - Files:   results/forgetting_curve.png
               results/accuracy_heatmap.png
               results/metrics_summary.png
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from data_gen import make_dataset, GENERATOR_NAMES
from fingerprint import extract_batch
from classifier import (
    new_classifier,
    naive_update,
    replay_update,
    ReplayBuffer,
    EWCProxyClassifier,
)
from evaluate import accuracy, forgetting_measure, backward_transfer, average_accuracy_at_stage, compute_full_metrics, print_metrics_table

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
N_GENERATORS = 5
N_TRAIN, N_TEST = 60, 30
CLASSES = np.array([0, 1])
OUT_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Build dataset
# ---------------------------------------------------------------------------
print("=" * 60)
print("  VERITAS — Continual Learning for AI-Image Detection")
print("=" * 60)
print("\nBuilding synthetic generator stream...")

train_sets, test_sets = [], []
for g in range(N_GENERATORS):
    Xtr_img, ytr = make_dataset(g, N_TRAIN // 2, N_TRAIN // 2, seed=g * 100 + 1)
    Xte_img, yte = make_dataset(g, N_TEST // 2, N_TEST // 2, seed=g * 100 + 2)
    train_sets.append((extract_batch(Xtr_img), ytr))
    test_sets.append((extract_batch(Xte_img), yte))

print(f"  {N_GENERATORS} generators | {N_TRAIN} train / {N_TEST} test samples each")
print(f"  Fingerprint feature dim: {train_sets[0][0].shape[1]}")

# ---------------------------------------------------------------------------
# Initialise strategies
# ---------------------------------------------------------------------------
clf_naive  = new_classifier(seed=1)
clf_replay = new_classifier(seed=1)
clf_ewc    = EWCProxyClassifier(ewc_lambda=5.0, seed=1)
buffer     = ReplayBuffer(cap_per_class=200, seed=1)

acc_naive  = np.zeros((N_GENERATORS, N_GENERATORS))
acc_replay = np.zeros((N_GENERATORS, N_GENERATORS))
acc_ewc    = np.zeros((N_GENERATORS, N_GENERATORS))

# ---------------------------------------------------------------------------
# Sequential training loop
# ---------------------------------------------------------------------------
print(f"\nSimulating {N_GENERATORS} generators arriving one at a time...\n")

for stage in range(N_GENERATORS):
    Xtr, ytr = train_sets[stage]
    gen_name = GENERATOR_NAMES[stage]

    # Update each strategy
    clf_naive  = naive_update(clf_naive, Xtr, ytr, CLASSES)
    clf_replay = replay_update(clf_replay, buffer, Xtr, ytr, CLASSES)
    if stage == 0:
        clf_ewc.fit(Xtr, ytr, CLASSES)
    else:
        clf_ewc.update(Xtr, ytr, CLASSES)

    # Evaluate all strategies on all generators seen so far
    for i in range(N_GENERATORS):
        Xte, yte = test_sets[i]
        acc_naive[i, stage]  = accuracy(clf_naive,  Xte, yte)
        acc_replay[i, stage] = accuracy(clf_replay, Xte, yte)
        acc_ewc[i, stage]    = accuracy(clf_ewc,    Xte, yte)

    print(f"── Stage {stage}: learned {gen_name} ──")
    seen = list(range(stage + 1))
    print(f"  Naive    acc: {[round(acc_naive[i, stage], 2) for i in seen]}")
    print(f"  Replay   acc: {[round(acc_replay[i, stage], 2) for i in seen]}")
    print(f"  EWC      acc: {[round(acc_ewc[i, stage], 2) for i in seen]}")
    print()

# ---------------------------------------------------------------------------
# Final metrics
# ---------------------------------------------------------------------------
metrics = {
    "Naive fine-tuning":  compute_full_metrics(acc_naive),
    "Replay (VERITAS)":   compute_full_metrics(acc_replay),
    "EWC-proxy":          compute_full_metrics(acc_ewc),
}

print("=" * 60)
print("  FINAL RESULTS")
print("=" * 60)
print_metrics_table(metrics)

# ---------------------------------------------------------------------------
# Plot 1: Forgetting curve (accuracy on generator-0 across all stages)
# ---------------------------------------------------------------------------
stages = list(range(N_GENERATORS))
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(stages, acc_naive[0],  marker="o", linewidth=2, label="Naive fine-tuning", color="#e74c3c")
ax.plot(stages, acc_replay[0], marker="s", linewidth=2, label="Replay (VERITAS)", color="#2ecc71")
ax.plot(stages, acc_ewc[0],    marker="^", linewidth=2, label="EWC-proxy", color="#3498db")
ax.set_xlabel("Stage (generator just learned)", fontsize=12)
ax.set_ylabel("Accuracy on Generator-0 test set", fontsize=12)
ax.set_title("Catastrophic Forgetting Curve\n(Generator 0 = StableDiffusion v1.5)", fontsize=13)
ax.set_ylim(0.35, 1.05)
ax.set_xticks(stages)
ax.set_xticklabels([f"S{s}\n({GENERATOR_NAMES[s][:6]}…)" for s in stages], fontsize=8)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
fig.tight_layout()
path1 = os.path.join(OUT_DIR, "forgetting_curve.png")
fig.savefig(path1, dpi=150)
plt.close(fig)
print(f"Saved → {path1}")

# ---------------------------------------------------------------------------
# Plot 2: Accuracy heat-maps (one per strategy)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(15, 4), sharey=True)
titles = ["Naive fine-tuning", "Replay (VERITAS)", "EWC-proxy"]
matrices = [acc_naive, acc_replay, acc_ewc]
gen_labels = [f"G{i}: {GENERATOR_NAMES[i][:8]}" for i in range(N_GENERATORS)]
stage_labels = [f"S{s}" for s in range(N_GENERATORS)]

for ax, mat, title in zip(axes, matrices, titles):
    masked = np.where(
        np.triu(np.ones_like(mat, dtype=bool), k=1),
        np.nan, mat
    )
    im = ax.imshow(masked, vmin=0.4, vmax=1.0, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(N_GENERATORS))
    ax.set_xticklabels(stage_labels, fontsize=9)
    ax.set_yticks(range(N_GENERATORS))
    ax.set_yticklabels(gen_labels, fontsize=9)
    ax.set_xlabel("Training Stage", fontsize=10)
    ax.set_title(title, fontsize=11, fontweight="bold")
    for i in range(N_GENERATORS):
        for j in range(N_GENERATORS):
            if j >= i:
                ax.text(j, i, f"{mat[i,j]:.2f}", ha="center", va="center", fontsize=8,
                        color="black")

fig.colorbar(im, ax=axes[-1], fraction=0.046, pad=0.04, label="Accuracy")
fig.suptitle("VERITAS — Accuracy Matrix A[generator][stage]", fontsize=13, fontweight="bold")
fig.tight_layout()
path2 = os.path.join(OUT_DIR, "accuracy_heatmap.png")
fig.savefig(path2, dpi=150)
plt.close(fig)
print(f"Saved → {path2}")

# ---------------------------------------------------------------------------
# Plot 3: Summary bar chart
# ---------------------------------------------------------------------------
strategy_names = list(metrics.keys())
avg_accs  = [metrics[s]["avg_accuracy"]       for s in strategy_names]
forgetting = [metrics[s]["forgetting_measure"] for s in strategy_names]

x = np.arange(len(strategy_names))
width = 0.35
colors_acc = ["#e74c3c", "#2ecc71", "#3498db"]
colors_fg  = ["#c0392b", "#27ae60", "#2980b9"]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

bars1 = ax1.bar(x, avg_accs, width, color=colors_acc, edgecolor="white", linewidth=1.2)
ax1.set_ylabel("Average Accuracy (↑ better)", fontsize=11)
ax1.set_title("Final Average Accuracy", fontsize=12, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels(strategy_names, fontsize=9, rotation=10, ha="right")
ax1.set_ylim(0, 1.1)
ax1.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
for bar, v in zip(bars1, avg_accs):
    ax1.text(bar.get_x() + bar.get_width() / 2, v + 0.01, f"{v:.1%}", ha="center", fontsize=10, fontweight="bold")
ax1.grid(axis="y", alpha=0.3)

bars2 = ax2.bar(x, forgetting, width, color=colors_fg, edgecolor="white", linewidth=1.2)
ax2.set_ylabel("Forgetting Measure (↓ better)", fontsize=11)
ax2.set_title("Catastrophic Forgetting", fontsize=12, fontweight="bold")
ax2.set_xticks(x)
ax2.set_xticklabels(strategy_names, fontsize=9, rotation=10, ha="right")
ax2.set_ylim(0, 0.5)
for bar, v in zip(bars2, forgetting):
    ax2.text(bar.get_x() + bar.get_width() / 2, v + 0.005, f"{v:.3f}", ha="center", fontsize=10, fontweight="bold")
ax2.grid(axis="y", alpha=0.3)

fig.suptitle("VERITAS — Strategy Comparison", fontsize=13, fontweight="bold")
fig.tight_layout()
path3 = os.path.join(OUT_DIR, "metrics_summary.png")
fig.savefig(path3, dpi=150)
plt.close(fig)
print(f"Saved → {path3}")

print("\nAll done. Run  python3 app.py  to launch the interactive demo.")
