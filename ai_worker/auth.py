
import os
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
import logging
import jwt
import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

def load_private_key_from_pem(pem_path):
    """Charge la clé privée depuis un fichier PEM"""
    try:
        with open(pem_path, "rb") as pem_file:
            pem_data = pem_file.read()
        private_key = load_pem_private_key(pem_data, password=None, backend=default_backend())
        logger.info(f"Private key loaded successfully: {private_key}")
        return private_key
    except Exception as e:
        logger.error(f"Erreur lors du chargement de la clé privée : {str(e)}")
        raise ValueError("Impossible de charger la clé privée")

async def get_jwt_token(application_name: str) -> str:
    """Génère un JWT signé avec la clé privée"""
    private_key = load_private_key_from_pem("./private_key.pem")
    try:
        logger.info("Starting to generate the JWT token with private key")
        
        if private_key is None:
            raise ValueError("Failed to load private key")
        
        keycloak_server_url = os.getenv('KEYCLOAK_SERVER_URL')
        logger.info(f"server url: {keycloak_server_url}")
        keycloak_realm = os.getenv('KEYCLOAK_REALM')
        logger.info(f"realm: {keycloak_realm}")
        
        if not keycloak_server_url or not keycloak_realm:
            raise ValueError("KEYCLOAK_SERVER_URL or KEYCLOAK_REALM environment variables are not set")
        
        payload = {
            "iss": application_name,
            "sub": application_name,
            "aud": f"{keycloak_server_url}/realms/{keycloak_realm}",
            "exp": int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)).timestamp()),
            "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        }
       
        token = jwt.encode(payload, private_key, algorithm="RS256")
        
        logger.info("JWT token generated successfully")
        logger.info(token)
        return token
    
    except Exception as e:
        logger.error(f"Error generating the JWT token: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating JWT: {str(e)}")

async def fetch_egm(episode_id: str, headers: dict):
    """Récupère l'EGM d'un épisode"""
    url = f"http://fastapi-app:8000/episode/{episode_id}/egm"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            logger.info(f"EGM obtenu avec succès pour episode_id: {episode_id}")
            return response.content
        else:
            logger.error(f"Erreur lors de l'obtention de l'EGM: {response.status_code} {response.text}")
            response.raise_for_status()

def get_mongodb_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(os.getenv('MONGODB_URL'))