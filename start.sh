#!/bin/sh
set -e

python manage.py migrate --noinput
python seed_data.py

exec gunicorn portal.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers 2 \
    --access-logfile - \
    --error-logfile -
