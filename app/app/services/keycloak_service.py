"""
Service for Keycloak interactions

BS 2024
"""

import httpx
from fastapi import HTTPException
import logging
import os
from typing import List

# Configuration détaillée du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class KeycloakService:
    def __init__(self):
        self.keycloak_url = os.getenv("KEYCLOAK_INTERNAL_SERVER_URL", "http://keycloak:8080")
        self.realm = os.getenv("KEYCLOAK_REALM", "pastec")
        self.admin_username = os.getenv("KEYCLOAK_ADMIN", "pastec-admin")
        self.admin_password = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "test")
        self.client_id = os.getenv("KEYCLOAK_CLIENT_ID_NUM", "367abfaa-b91c-44d9-9b39-a87bb05e03ab")
        # Log des variables d'environnement (en masquant le mot de passe)
        logger.debug(f"Keycloak URL: {self.keycloak_url}")
        logger.debug(f"Realm: {self.realm}")
        logger.debug(f"Admin username: {self.admin_username}")
        logger.debug(f"Admin password length: {len(self.admin_password) if self.admin_password else 0}")

    async def get_admin_token(self) -> str:
        """Obtenir un token d'accès admin pour l'API Keycloak"""
        token_url = f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": self.admin_username,
            "password": self.admin_password
        }
        
        logger.debug(f"Attempting to get admin token from: {token_url}")
        logger.debug(f"Request data (excluding password): {dict(data, password='*****')}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug("Sending token request...")
                response = await client.post(token_url, data=data)
                
                logger.debug(f"Token response status: {response.status_code}")
                logger.debug(f"Token response headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    logger.error(f"Failed to get Keycloak admin token: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    logger.error(f"Request URL: {token_url}")
                    logger.error(f"Request headers: {dict(response.request.headers)}")
                    raise HTTPException(500, "Failed to get Keycloak admin token")
                
                token_data = response.json()
                logger.debug("Successfully obtained admin token")
                return token_data["access_token"]
                
        except httpx.RequestError as e:
            logger.error(f"HTTP Request failed: {str(e)}")
            raise HTTPException(500, f"Failed to connect to Keycloak: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during token request: {str(e)}", exc_info=True)
            raise HTTPException(500, f"Unexpected error: {str(e)}")

    async def get_ai_users(self, manufacturer: str, episode_type: str) -> List[str]:
        """Vérifier les utilisateurs IA disponibles pour un type d'épisode"""
        try:
            logger.info(f"Searching AI users for manufacturer: {manufacturer}, episode_type: {episode_type}")
            token = await self.get_admin_token()
            role_name = f"ai_model.{manufacturer.lower()}.{episode_type}"
            
            users_url = f"{self.keycloak_url}/admin/realms/{self.realm}/clients/{self.client_id}/roles/{role_name}/users"
            logger.debug(f"Requesting users for role: {role_name}")
            logger.debug(f"Users URL: {users_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {token}"}
                logger.debug(f"Request headers: {headers}")
                
                response = await client.get(users_url, headers=headers)
                
                logger.debug(f"Users response status: {response.status_code}")
                logger.debug(f"Users response headers: {dict(response.headers)}")
                
                if response.status_code == 404:
                    logger.info(f"Rôle {role_name} non trouvé")
                    return []
                elif response.status_code != 200:
                    logger.error(f"Erreur lors de la requête Keycloak: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return []
                
                users = response.json()
                logger.info(f"Found {len(users)} users with role {role_name}")
                return [user["username"] for user in users if user.get("username")]
                
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des utilisateurs IA: {str(e)}", exc_info=True)
            return [] 