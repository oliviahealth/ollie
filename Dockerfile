FROM python:3.11-slim

WORKDIR /app

# ---- system deps ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    postgresql-client \
    poppler-utils \
    tesseract-ocr \
  && rm -rf /var/lib/apt/lists/*

# ---- python deps ----
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    python -c "import nltk; nltk.download('punkt_tab', download_dir='/usr/local/share/nltk_data'); nltk.download('punkt', download_dir='/usr/local/share/nltk_data')"

# ---- patched flask-admin ----
COPY packages/flask-admin /deps/flask-admin
RUN pip uninstall -y flask-admin || true && \
    pip install --no-deps -e /deps/flask-admin

# ---- app code ----
COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PORT=5050

EXPOSE 5050

CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:5050", "main:app"]