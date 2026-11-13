FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# curl + CLI Docker : le CLI sert au SCAN HÉBERGÉ (la plateforme lance des conteneurs cibles)
RUN apt-get update \
 && apt-get install -y --no-install-recommends docker.io curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p reports

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]