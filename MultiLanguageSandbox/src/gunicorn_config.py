#!/usr/bin/env python3
timeout = 60  # 设置 worker 超时时间为 60 秒
import logging
from logging.handlers import RotatingFileHandler

log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
accesslog = '/data/logs/http.log'
errorlog = '/data/logs/error.log'

# 配置访问日志轮转
access_handler = RotatingFileHandler(
    filename=accesslog,
    maxBytes=1024 * 1024 * 1024,  # 1GB 轮转
    backupCount=7               # 保留7个备份
)
access_handler.setFormatter(logging.Formatter(log_format))
