# VERITAS
### Continual Learning Framework for AI-Generated Image Detection

> **PBL Project — AI & ML, 2026**

---

## Problem Statement

New AI image generators keep launching. A detector trained today fails on tomorrow's brand-new generator. And if you try to teach it the new one, it **catastrophically forgets** what it knew about older ones.

## Solution

VERITAS identifies AI-generated images using **diffusion reconstruction fingerprinting** and **incrementally adapts** to new generators over time — without forgetting previously learned ones.

---

## 4 Modules

| # | Module | What it does |
|---|--------|-------------|
| 1 | **Fingerprint Extraction** | Runs images through multi-strength reconstruction; real vs AI react differently |
| 2 | **Baseline Classifier** | Random Forest on fingerprint features → real/fake prediction |
| 3 | **Continual Learning** | Replay buffer keeps old generator memory while learning new ones |
| 4 | **Evaluation** | Accuracy + Forgetting Measure across sequential generator stream |

---

## Results (5 Generators, Sequential)

| Strategy | Avg Accuracy ↑ | Forgetting ↓ |
|----------|----------------|--------------|
| Naive fine-tuning | 68.7% | 0.392 |
| **Replay — VERITAS** | **95.3%** | **0.050** |
| EWC-proxy | 50.0% | 0.000 |

VERITAS achieves **+26.6% accuracy** and **87% less forgetting** than the naive baseline.

---

## Quick Start

```bash
# 1. Install dependencies
pip3 install numpy scikit-learn matplotlib seaborn streamlit plotly

# 2. Run the experiment (generates plots in results/)
python3 main.py

# 3. Launch the interactive demo
streamlit run app.py
# → Open http://localhost:8501
```

Or just run:
```bash
bash run_demo.sh
```

---

## Project Structure

```
PROJECT VERITAS/
├── data_gen.py       # Module: Synthetic dataset (5 AI generators)
├── fingerprint.py    # Module 1: Reconstruction fingerprint extraction
├── classifier.py     # Module 2+3: Classifier + continual learning strategies
├── evaluate.py       # Module 4: Accuracy & forgetting metrics
├── main.py           # Experiment runner (generates plots)
├── app.py            # Streamlit interactive demo
├── run_demo.sh       # One-click startup script
└── results/          # Generated plots (after running main.py)
    ├── forgetting_curve.png
    ├── accuracy_heatmap.png
    └── metrics_summary.png
```

---

## How it Works

**Fingerprint Extraction:** Every AI generator leaves a characteristic frequency pattern on its images. We reveal it by running the image through a reconstruction process at multiple strengths (blur levels, analogous to diffusion noise levels) and measuring the residuals. Real photos and AI-generated images react differently.

**Continual Learning (Replay):** When a new generator arrives, we retrain the classifier on new data **plus** a replay buffer of examples from every old generator. This prevents catastrophic forgetting — the model remembers what it already knew.

**Evaluation:** After training on all 5 generators sequentially, we measure:
- **Average Accuracy** — can the model catch fakes from all generators?
- **Forgetting Measure** — how much did it forget about older generators?
