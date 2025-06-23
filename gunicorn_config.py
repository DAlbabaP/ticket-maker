# Gunicorn configuration file
bind = "0.0.0.0:10000"
workers = 2
worker_class = "sync"
timeout = 120
max_requests = 1000
max_requests_jitter = 100
keepalive = 2
