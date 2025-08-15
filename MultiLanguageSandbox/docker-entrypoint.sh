#!/bin/bash
set -e

echo "PATH is: $PATH"

# 启动 Gunicorn（前台主进程）
exec gunicorn -c /data/gunicorn_config.py \
  -w 16 --threads 1 \
  -b 0.0.0.0:8080 \
  sandbox:app