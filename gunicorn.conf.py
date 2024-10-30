import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"

# Worker processes
workers = 1
worker_class = 'sync'
worker_timeout = 120  # Increase timeout to 120 seconds

# Logging
loglevel = 'info'
accesslog = '-'
errorlog = '-'

# Process naming
proc_name = 'gunicorn_application'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None