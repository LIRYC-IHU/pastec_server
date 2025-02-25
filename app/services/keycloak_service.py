"""
Service for Keycloak interactions

BS 2024
"""

import httpx
from fastapi import HTTPException
import logging
import os
from typing import List, Dict

# Configuration détaillée du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class KeycloakService:
    def __init__(self):
        self.keycloak_url = os.getenv("KEYCLOAK_INTERNAL_SERVER_URL")
        self.realm = os.getenv("KEYCLOAK_REALM", "pastec")
        self.admin_username = os.getenv("KEYCLOAK_PASTEC_ADMIN")
        self.admin_password = os.getenv("KEYCLOAK_PASTEC_ADMIN_PASSWORD")
        self.client_id = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")  # Par défaut admin-cli
        self.client_secret = os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET", None)  # Ajouter le secret
        # Log des variables d'environnement (en masquant le mot de passe et le secret)
        logger.info(f"Keycloak URL: {self.keycloak_url}")
        logger.info(f"Realm: {self.realm}")
        logger.info(f"Admin username: {self.admin_username}")
        logger.info(f"Admin client ID: {self.client_id}")
        logger.info(f"Admin client secret length: {len(self.client_secret) if self.client_secret else 0}")

    async def get_admin_token(self) -> str:
        
        # Vérification des variables chargées
        """Obtenir un token d'accès admin pour l'API Keycloak"""
        logger.debug("Getting admin token...")
        logger.debug(f"Keycloak URL: {self.keycloak_url}")
        logger.debug(f"Realm: {self.realm}")
        logger.debug(f"Admin username: {self.admin_username}")  
        logger.debug(f"Admin client ID: {self.client_id}")
        logger.debug(f"Admin client secret length: {len(self.client_secret) if self.client_secret else 0}")
        token_url = f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": self.admin_username,
            "password": self.admin_password
        }

        # Inclure le client_secret si le client est confidentiel
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        logger.debug(f"Attempting to get admin token from: {token_url}")
        logger.debug(f"Request data (excluding password and client_secret): {dict(data, password='*****', client_secret='*****')}")
        
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


    async def get_ai_clients(self, manufacturer: str, episode_type: str) -> List[Dict[str, str]]:
        """Vérifier les clients IA disponibles pour un type d'épisode"""
        try:
            logger.info(f"Searching AI users for manufacturer: {manufacturer}, episode_type: {episode_type}")
            token = await self.get_admin_token()
            role_name = f"{manufacturer.lower()}.{episode_type}"
            
            clients_url = f"{self.keycloak_url}/admin/realms/{self.realm}/clients"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {token}"}
                logger.debug(f"Request headers: {headers}")
                
                response = await client.get(clients_url, headers=headers)
                
                logger.debug(f"clients response status: {response.status_code}")
                logger.debug(f"clients response headers: {dict(response.headers)}")
                
                if response.status_code == 404:
                    logger.info(f"Rôle {role_name} non trouvé")
                    return []
                elif response.status_code != 200:
                    logger.error(f"Erreur lors de la requête Keycloak: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return []
                
                clients = response.json()
                client_list = []
                
                for client in clients:
                    if client.get("serviceAccountsEnabled"):
                        client_list.append({"client_id": client.get("id"), "client_name": client.get("clientId")})

                logger.info(f"Found {len(client_list)} clients")  
                logger.info(client_list)           
                
                return client_list
                
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des utilisateurs IA: {str(e)}", exc_info=True)
            return [] 
        
    async def get_ai_client_roles(self, ai_client: Dict[str, str]) -> Dict[str, List[str]]:
        """Obtenir les rôles d'un client IA"""
        """format de ai_client: {client_id: client_name}

        Returns:
            client_name: [roles]
        """
        try:
            token = await self.get_admin_token()
            client_id = ai_client["client_id"]
            client_name = ai_client["client_name"]
            
            account_id_url = f"{self.keycloak_url}/admin/realms/{self.realm}/clients/{client_id}/service-account-user"
            logger.debug(f"Roles URL: {account_id_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {token}"}
                logger.debug(f"Request headers: {headers}")
                
                response = await client.get(account_id_url, headers=headers)
                
                logger.debug(f"Roles response status: {response.status_code}")
                logger.debug(f"Roles response headers: {dict(response.headers)}")
                
                if response.status_code == 404:
                    logger.info(f"Client {client_id} not found")
                    return {}
                elif response.status_code != 200:
                    logger.error(f"Erreur lors de la requête Keycloak: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return {}
                
                service_account = response.json()
                
                logger.debug(f"Service account: {service_account}")
                
                roles_url = f"{self.keycloak_url}/admin/realms/{self.realm}/users/{service_account['id']}/role-mappings"
                
                response = await client.get(roles_url, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"Erreur lors de la recherche des rôles du client IA: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return {}
            
                role_response = response.json()
                
                roles = [role["name"] for role in role_response.get("realmMappings", [])] 
                logger.info(f"Found {len(roles)} roles")
            
                return {client_name: roles}
                
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des rôles du client IA: {str(e)}", exc_info=True)
            return {}