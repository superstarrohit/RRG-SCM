#!/bin/sh
set -e

if [ ! -f /app/data/rrg_scm.db ]; then
  echo "No existing database found — seeding sample data..."
  python -m scripts.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
