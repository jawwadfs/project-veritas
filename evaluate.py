"""
Module 4: Generalization Evaluation
====================================
Computes the metrics that actually prove (or disprove) the continual learning claim.

Key metrics
-----------
- Accuracy matrix A[i][j]  : accuracy on generator i's test set, measured
                             immediately after training stage j.
- Average Accuracy (AA)    : mean accuracy across all seen generators at the
                             final stage — overall capability score.
- Forgetting Measure (FM)  : average drop in accuracy from each generator's
                             peak to the final stage — memory retention score.
                             Lower is better.  0.0 = perfect memory.
- Backward Transfer (BWT)  : signed version of FM; negative values confirm
                             catastrophic forgetting.
- Intransigence (I)        : how much harder it became to learn new generators
                             as the model accumulated old knowledge.
"""

import numpy as np
from typing import List


def accuracy(clf, X: np.ndarray, y: np.ndarray) -> float:
    """Classification accuracy on a held-out test set."""
    preds = clf.predict(X)
    return float((preds == y).mean())


def forgetting_measure(accuracy_matrix: np.ndarray) -> float:
    """
    For each generator i (except the last), compute:
        forgetting_i = max_{j>=i} A[i][j] − A[i][-1]
    Average over all generators that had a chance to be forgotten.

    Returns a value in [0, 1]; lower is better.
    """
    n_gens = len(accuracy_matrix)
    forgetting: List[float] = []
    for i in range(n_gens - 1):
        row = accuracy_matrix[i]
        best = max(row[i:])      # best accuracy from when it was first learned
        final = row[-1]
        forgetting.append(best - final)
    return float(np.mean(forgetting)) if forgetting else 0.0


def backward_transfer(accuracy_matrix: np.ndarray) -> float:
    """
    BWT = mean of (A[i][-1] - A[i][i]) for i < n_gens-1.
    Negative values confirm catastrophic forgetting.
    """
    n_gens = len(accuracy_matrix)
    bwt: List[float] = []
    for i in range(n_gens - 1):
        bwt.append(accuracy_matrix[i][-1] - accuracy_matrix[i][i])
    return float(np.mean(bwt)) if bwt else 0.0


def average_accuracy_at_stage(accuracy_matrix: np.ndarray, stage: int) -> float:
    """Mean accuracy across all generators seen so far, at a given stage."""
    vals = [
        accuracy_matrix[i][stage]
        for i in range(len(accuracy_matrix))
        if stage >= i
    ]
    return float(np.mean(vals)) if vals else 0.0


def compute_full_metrics(accuracy_matrix: np.ndarray) -> dict:
    """Return all evaluation metrics in one call."""
    n_gens = accuracy_matrix.shape[0]
    final_stage = n_gens - 1
    return {
        "avg_accuracy":       average_accuracy_at_stage(accuracy_matrix, final_stage),
        "forgetting_measure": forgetting_measure(accuracy_matrix),
        "backward_transfer":  backward_transfer(accuracy_matrix),
        "per_generator_final": [
            float(accuracy_matrix[i][final_stage]) for i in range(n_gens)
        ],
    }


def print_metrics_table(metrics_dict: dict, label_width: int = 22) -> None:
    """Pretty-print a comparison table of metrics across strategies."""
    strategies = list(metrics_dict.keys())
    print(f"\n{'Strategy':<{label_width}}  {'Avg Acc':>8}  {'Forgetting':>10}  {'BWT':>8}")
    print("-" * (label_width + 32))
    for strat in strategies:
        m = metrics_dict[strat]
        print(
            f"{strat:<{label_width}}  "
            f"{m['avg_accuracy']:>8.3f}  "
            f"{m['forgetting_measure']:>10.3f}  "
            f"{m['backward_transfer']:>8.3f}"
        )
    print()
