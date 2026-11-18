#!/usr/bin/env bash
# VERITAS — Quick Start
cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   VERITAS — AI Image Detection System        ║"
echo "║   Continual Learning Framework Demo          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check dataset
REAL_COUNT=$(ls data/real/*.png 2>/dev/null | wc -l | tr -d ' ')
if [ "$REAL_COUNT" -lt "50" ]; then
    echo "▶ Dataset not found. Downloading CIFAKE (needs internet)..."
    python3 download_data.py
else
    echo "✅  Dataset ready ($REAL_COUNT real images)"
fi

echo ""
echo "▶ Launching interactive demo..."
echo "   Open: http://localhost:8501"
echo ""

python3 -m streamlit run app.py --server.port 8501
