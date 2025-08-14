#!/usr/bin/env bash
DIR="/home/centos/RAGBOX/Agency/Shinhwa/offboarding"
exec "$DIR/.venv/bin/streamlit" run "$DIR/app.py" --server.port 8013 --server.address 0.0.0.0 --server.headless true
