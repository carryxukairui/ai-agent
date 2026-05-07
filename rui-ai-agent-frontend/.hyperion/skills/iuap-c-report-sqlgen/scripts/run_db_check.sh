#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python3 db_query.py --config ../config.yaml --query elastic_field_check
