#!/bin/sh


# Container entrypoint script
# Responsibilities:
# - Wait for database readiness
# - Run migrations
# - Seed initial data
# - Start application
#
# Designed to work in ECS Fargate environment

set -e

echo "Waiting for database..."

while ! python -c "
import socket
import os
import json

secrets_json = os.environ.get('secrets_json', '{}')
try:
    aws_secrets = json.loads(secrets_json)
    host = aws_secrets.get('db_host')
    port = aws_secrets.get('db_port', 5432)
except Exception as e:
    exit(1)

if not host:
    exit(1)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
try:
    s.connect((host, int(port)))
    s.close()
except:
    exit(1)
" > /dev/null 2>&1; do
  echo "Database is not ready yet (checking db_host) - sleeping 4s..."
  sleep 4
done

echo "Database is UP! Starting preparations..."

if [ "$#" -gt 0 ]; then
    echo "Custom command detected: $@"
    exec "$@"
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Seeding Allegro credentials..."
python manage.py setup_allegro_cred

if [ "$ENVIRONMENT" = "production" ]; then
    echo "Starting production server (gunicorn)..."
    exec gunicorn allegro.wsgi:application --bind 0.0.0.0:8000
else
    echo "Starting development server..."
    exec python manage.py runserver 0.0.0.0:8000
fi
