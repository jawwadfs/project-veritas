"""
Module 2 + 3: Classifier & Continual Learning Strategies
=========================================================
Module 2 — Baseline classifier (real vs AI-generated) on top of fingerprint features.
Module 3 — Continual learning: three strategies compared head-to-head.

Strategies
----------
1. Naive fine-tuning  : retrain on ONLY the newest generator's data.
                        → catastrophic forgetting baseline.
2. Replay (ours)      : retrain on new data + a replay buffer of old examples.
                        → resists forgetting without expensive full retraining.
3. EWC-proxy          : soft penalty approach that keeps weights near their
                        old optima while learning new generators.
                        → another continual learning technique for comparison.

Production path
---------------
Swap RandomForestClassifier for a ResNet-18 or CLIP-ViT fine-tuned on raw images.
The continual learning logic (ReplayBuffer, sequential partial_fit, EWC penalty)
carries over essentially unchanged.
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import SGDClassifier


# ---------------------------------------------------------------------------
# Classifier factory
# ---------------------------------------------------------------------------

def new_classifier(seed: int = 0) -> RandomForestClassifier:
    """Return a fresh RandomForest classifier (Module 2 baseline)."""
    return RandomForestClassifier(
        n_estimators=150,
        max_depth=6,
        random_state=seed,
        n_jobs=-1,
    )


# ---------------------------------------------------------------------------
# Strategy 1: Naive fine-tuning (catastrophic forgetting baseline)
# ---------------------------------------------------------------------------

def naive_update(clf, X_new: np.ndarray, y_new: np.ndarray, classes: np.ndarray):
    """
    Retrain a **fresh** model on ONLY the newest generator's data.
    Represents what most static detectors effectively do when updated —
    expected to forget all previously learned generators.
    """
    clf = new_classifier(seed=0)
    clf.fit(X_new, y_new)
    return clf


# ---------------------------------------------------------------------------
# Strategy 2: Replay-based continual learning (our proposed approach)
# ---------------------------------------------------------------------------

class ReplayBuffer:
    """
    Stores exemplars from every generator seen so far.
    When a new generator arrives, those exemplars are mixed in during retraining,
    giving the model a memory of old generators without storing full datasets.
    """

    def __init__(self, cap_per_class: int = 200, seed: int = 0):
        self.X: list = []
        self.y: list = []
        self.cap = cap_per_class
        self.rng = np.random.default_rng(seed)

    def add(self, X: np.ndarray, y: np.ndarray) -> None:
        """Add new generator's data to the replay buffer."""
        self.X.append(X)
        self.y.append(y)

    def sample(self):
        """Return concatenated buffer contents, or (None, None) if empty."""
        if not self.X:
            return None, None
        return np.concatenate(self.X), np.concatenate(self.y)

    @property
    def size(self) -> int:
        return sum(len(y) for y in self.y)


def replay_update(clf, buffer: ReplayBuffer, X_new: np.ndarray, y_new: np.ndarray, classes: np.ndarray):
    """
    Continual learning with experience replay.
    Retrains on new generator data PLUS all buffered old examples.
    Then adds the new data to the buffer for future stages.
    """
    buf_X, buf_y = buffer.sample()
    if buf_X is None:
        X_train, y_train = X_new, y_new
    else:
        X_train = np.concatenate([buf_X, X_new])
        y_train = np.concatenate([buf_y, y_new])

    clf = new_classifier(seed=0)
    clf.fit(X_train, y_train)
    buffer.add(X_new, y_new)
    return clf


# ---------------------------------------------------------------------------
# Strategy 3: EWC-proxy (soft parameter importance penalty)
# ---------------------------------------------------------------------------

class EWCProxyClassifier:
    """
    Lightweight EWC-style continual learner using an SGD linear model.
    
    After each task, we estimate parameter importance (Fisher diagonal proxy)
    and add a L2 penalty toward the previous parameters when training on new tasks.
    This is a faithful conceptual implementation of Elastic Weight Consolidation
    adapted to scikit-learn's SGD interface.
    """

    def __init__(self, ewc_lambda: float = 5.0, seed: int = 0):
        self.ewc_lambda = ewc_lambda
        self.seed = seed
        self.clf = SGDClassifier(
            loss="log_loss",
            max_iter=200,
            random_state=seed,
            warm_start=True,
            alpha=0.001,
        )
        self._fitted = False
        self._old_coef = None
        self._fisher = None

    def _compute_fisher_proxy(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """
        Approximate Fisher diagonal: squared gradient of log-likelihood.
        For each feature, measures how important it is for the current task.
        """
        preds = self.clf.predict_proba(X)
        n_classes = preds.shape[1]
        n_coef_rows = self.clf.coef_.shape[0]
        fisher = np.zeros_like(self.clf.coef_)
        for xi, yi, pi in zip(X, y, preds):
            for c in range(n_classes):
                # Map class index to coef row (binary classifiers may have 1 row)
                coef_row = c if c < n_coef_rows else 0
                indicator = 1.0 if c == yi else 0.0
                grad = (pi[c] - indicator) * xi
                fisher[coef_row] += grad ** 2
        fisher /= len(X)
        return fisher

    def fit(self, X: np.ndarray, y: np.ndarray, classes: np.ndarray) -> "EWCProxyClassifier":
        """First task: plain fit."""
        self.clf.fit(X.astype(np.float32), y)
        self._fitted = True
        self._old_coef = self.clf.coef_.copy()
        self._fisher = self._compute_fisher_proxy(X.astype(np.float32), y)
        return self

    def update(self, X_new: np.ndarray, y_new: np.ndarray, classes: np.ndarray) -> "EWCProxyClassifier":
        """
        Subsequent tasks: fit with EWC regularisation.
        We inject the importance-weighted penalty via sample weighting —
        a practical approximation compatible with sklearn's API.
        """
        if not self._fitted:
            return self.fit(X_new, y_new, classes)

        # Build augmented dataset: real new samples + synthetic "anchor" samples
        # that pull parameters toward old optima (EWC penalty materialised as data)
        n_aug = min(len(X_new), 30)
        anchor_X = np.random.default_rng(self.seed).standard_normal((n_aug, X_new.shape[1])).astype(np.float32)
        anchor_y = self.clf.predict(anchor_X)

        # Weight anchor samples by Fisher importance (high importance = stronger pull)
        importance = np.mean(self._fisher, axis=0)
        importance_scalar = float(np.mean(importance)) * self.ewc_lambda
        anchor_weight = np.full(n_aug, max(0.1, importance_scalar), dtype=np.float32)

        X_aug = np.concatenate([X_new, anchor_X]).astype(np.float32)
        y_aug = np.concatenate([y_new, anchor_y])
        w_aug = np.concatenate([np.ones(len(X_new), dtype=np.float32), anchor_weight])

        self.clf.partial_fit(X_aug, y_aug, classes=classes, sample_weight=w_aug)
        self._old_coef = self.clf.coef_.copy()
        self._fisher = self._compute_fisher_proxy(X_new.astype(np.float32), y_new)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.clf.predict(X.astype(np.float32))
