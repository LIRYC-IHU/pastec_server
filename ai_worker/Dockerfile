FROM python:3.9-slim

WORKDIR /ai_worker

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y --fix-missing --allow-unauthenticated \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Création du répertoire ai_models et copie des scripts
RUN mkdir -p /ai_worker/ai_models
COPY ./ai_models /ai_worker/ai_models

# Copie du reste du code source
COPY . .

EXPOSE 8001

# Lancement direct d'uvicorn avec les bons paramètres
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--log-level", "debug", "--reload-dir", "/ai_worker"]