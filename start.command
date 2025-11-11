#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python -m streamlit run streamlit_app.py --server.port 8503
