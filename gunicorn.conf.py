"""One process owns the shared project, AI plans, and export jobs."""
import os

bind = f"0.0.0.0:{int(os.environ.get('PORT', '10000'))}"
workers = 1
worker_class = "gthread"
threads = 8
timeout = 180
graceful_timeout = 120
keepalive = 5
preload_app = False
accesslog = "-"
errorlog = "-"
capture_output = True
# Only log the path: setup keys or other query parameters must not enter logs.
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
