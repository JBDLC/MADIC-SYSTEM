# MADIC SYSTEM - Deploy sur Render (Python 3.11 fixe)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["/bin/sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000}"]
