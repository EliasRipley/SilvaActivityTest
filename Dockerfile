FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8080

CMD python manage.py migrate --noinput && python seed_data.py && exec gunicorn portal.wsgi:application --bind 0.0.0.0:8080 --workers 2
