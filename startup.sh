#!/bin/bash
set -e
source /antenv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
