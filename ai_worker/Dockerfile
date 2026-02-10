FROM python:3.9-slim

WORKDIR /ai_worker

ENV DEBIAN_FRONTEND=noninteractive \
    APT_FLAGS="-o Acquire::Retries=5 -o Acquire::http::Timeout=30"

# Force apt to use IPv4 if IPv6 is flaky in your env
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

RUN apt-get update && apt-get upgrade -y

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    libsndfile1-dev \
    libsndfile1 \
    libxml2-dev \
    libxslt1-dev \
    ffmpeg \
    build-essential \
    && apt-get clean

# Copie des fichiers de requirements

# Installer les dépendances avant de copier tout le code
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt


# Création du répertoire ai_models et copie des scripts
RUN mkdir -p /ai_worker/ai_models
COPY ./ai_models /ai_worker/ai_models

# Copie du reste du code source
COPY . .

EXPOSE 8001

# Lancement direct d'uvicorn avec les bons paramètres
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--log-level", "debug", "--reload-dir", "/ai_worker"]