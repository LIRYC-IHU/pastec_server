"""
Service for Keycloak interactions

BS 2024

"""

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Union
from keycloak import KeycloakAdmin, KeycloakOpenIDConnection
import logging
import os
from typing import List, Dict
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
import datetime
from db import UserEntry

# Configuration détaillée du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_keycloak_admin(client = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")) -> KeycloakAdmin:
    """
    Crée et retourne un client KeycloakAdmin configuré
    à partir des variables d'environnement.
    On désactive l'auto-refresh du token pour les clients publics.
    """
    kc = KeycloakAdmin(
        server_url=os.getenv("KEYCLOAK_INTERNAL_SERVER_URL"),
        username=os.getenv("KEYCLOAK_PASTEC_ADMIN"),
        password=os.getenv("KEYCLOAK_PASTEC_ADMIN_PASSWORD"),
        realm_name=os.getenv("KEYCLOAK_REALM"),
        client_id=client,
        # pas de client_secret_key pour garder le mode public
        verify=True,
    )
    # désactive le rafraîchissement automatique du token
    try:
        kc.connection.auto_refresh_token = False
    except AttributeError:
        # pour les versions sans auto_refresh_token, ignore
        pass
    return kc

def generate_certificate(subject: str, public_key, private_key, issuer: str= 'PASTEC Corp') -> x509.Certificate:
    """
    Génère un certificat X.509 auto-signé.
    
    Args:
        subject (str): Le nom du sujet du certificat.
        issuer (str): Le nom de l'émetteur du certificat.
        public_key: La clé publique à inclure dans le certificat.
        private_key: La clé privée pour signer le certificat.
    
    Returns:
        x509.Certificate: Le certificat auto-signé.
    """
    subject_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, subject),
    ])
    
    issuer_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, issuer),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject_name)
        .issuer_name(issuer_name)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )
    
    return cert

async def upload_key(client_id: str) -> Union[bytes, JSONResponse]:
        
        kc = get_keycloak_admin()
        
        ## get client uuid
        
        uuid = kc.get_client_id(client_id)
        if not uuid:
            logger.error(f"Client {client_id} not found")
            return JSONResponse(status_code=404, content={"error": "Client not found"})
        
        logger.info(f"Client UUID for {client_id}: {uuid}")
        
        # Générer une paire de clés RSA
        private_key, public_key = generate_keys()
        certificate = generate_certificate(
            subject=client_id,
            public_key=public_key,
            private_key=private_key
        )
        
        logger.info("Generated RSA key pair")
        
        # Convertir la clé publique en PEM
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        certificate_pem = certificate.public_bytes(
            encoding=serialization.Encoding.PEM
        )
        logger.info("Converted public key to PEM format")
        
        logger.info(f"certificate content: {certificate_pem.decode('utf-8')}")
        
        try:
            dict = kc.upload_certificate(uuid, certificate_pem.decode('utf-8'))
            logger.info(f"Keycloak response: {dict}")
            logger.info(f"Key uploaded successfully for client {client_id}")
            return private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        except Exception as e:
            logger.error(f"Failed to upload key for client {client_id}: {str(e)}")
            return JSONResponse(status_code=500, content={"error": "Failed to upload key"})
        
def generate_keys():
    """Générer une paire de clés RSA pour le client"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    
    return private_key, public_key
    
async def create_new_user(user: UserEntry) -> JSONResponse:
    """
    Crée un nouvel utilisateur dans Keycloak.
    
    Args:
        user (UserEntry): L'utilisateur à créer.
        
    Returns:
        JSONResponse: La réponse de l'API Keycloak.
    """
    kc = get_keycloak_admin()
    
    try:
        
        logger.info('user center: %s', user.center.value)
        logger.info('user user_type: %s', user.user_type.value)
        
        user_id = kc.create_user({
            "email": user.email,
            "username": user.username,
            "enabled": True,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "credentials": [{"value": user.password,"type": "password"}],
            }
        )

        logger.info(f"User {user.username} created successfully")
        
        logger.info(f"User ID: {user_id}")
        
        
        groups = kc.get_groups()  # liste de dicts { "id", "name", "path", ... }
        group = next(g for g in groups if g["name"] == user.center.value)
        kc.group_user_add(user_id, group["id"])
        logger.info(f"Added user {user.username} to group {group['name']}")
        
        client_uuid = kc.get_client_id(os.getenv("KEYCLOAK_CLIENT_ID"))  
        role_def    = kc.get_client_role(client_uuid, user.user_type.value)
        kc.assign_client_role(
            user_id,                # l’utilisateur
            client_uuid,            # le client (ex: "pastec-server")
            [role_def]              # liste des rôles à ajouter
        )
        logger.info(f"Assigned client-role {role_def['name']} to user {user.username}")
        
        
        return JSONResponse(status_code=201, content={"message": f"User {user.username} created successfully"})
        
    except Exception as e:
        logger.error(f"Failed to create user {user.username}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
async def register_new_model(roles: List[str], model_name: str, description: str = 'no description available') -> JSONResponse:
        """Enregistrer un nouveau modèle dans Keycloak"""
        try:
            kc = get_keycloak_admin()
            
            payload = {
                "name": model_name,
                "description": description,
                "clientId": model_name,
                "clientAuthenticatorType": "client-jwt",
                "enabled": True,
                "protocol": "openid-connect",
                "serviceAccountsEnabled": True,
                "publicClient": False,
                "consentRequired": False,
                "standardFlowEnabled": False,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False,
            }
            
            logger.info(f"Registering new model with payload: {payload}")
            client_uuid = kc.create_client(payload)
            logger.info(f"Model {model_name} registered successfully: {client_uuid}")
            logger.info("trying to add roles to service account")
            response = assign_roles_to_service_account(kc, client_uuid, roles )
            return JSONResponse(status_code=201, content={"message": "Model registered successfully", "client_id": client_uuid})
        except HTTPException as e:
            logger.error(f"Failed to get admin token: {str(e)}")
            return JSONResponse(status_code=500, content={"error": "Failed to get admin token"})
        
def get_client_rep(client_id: str) -> dict:
    """Obtenir la représentation d'un client"""
    try:
        kc = get_keycloak_admin()
        client_uuid = kc.get_client_id(client_id)
        
        if not client_uuid:
            logger.error(f"Client {client_id} not found")
            raise HTTPException(status_code=404, detail="Client not found")
        logger.info(f"realm roles for client {client_id}: {realm_roles}")
        
        return kc.get_client(client_uuid)

    except Exception as e:
        logger.error(f"Error getting client representation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: Failed to get client representation, {str(e)}")

def assign_roles_to_service_account(kc: KeycloakAdmin, client_uuid: str, roles: List[str]) -> JSONResponse:  

    sa_user = kc.get_client_service_account_user(client_uuid)
    user_id = sa_user.get("id")
    if not user_id:
        raise HTTPException(status_code=404, detail="Service-account non trouvé")

    # 3) Récupérer tous les realm-roles existants
    existing_roles = {r["name"] for r in kc.get_realm_roles()}
    missing_roles = set(roles) - existing_roles
    logger.info(f"Existing realm roles: {existing_roles}")
    logger.info(f"{len(missing_roles)} roles are missing: {missing_roles}")

    # 5) Assigner chaque rôle existant
    for role_name in existing_roles:
        realm_role = kc.get_realm_role(role_name)
        kc.assign_realm_roles(user_id, [realm_role])

    logger.info(f"Assigned realm roles {existing_roles} to service-account '{client_uuid}'")
    
def get_clients_with_realm_role(role_name: str) -> List[Dict[str, str]]:
    """
    Retourne la liste des clients (service accounts) dont le service-account
    possède le realm-role spécifié.
    """
    kc = get_keycloak_admin()
    matching_clients: List[Dict[str, str]] = []

    # Récupère tous les clients du realm
    all_clients = kc.get_clients()
    for client in all_clients:
        # Ne considérer que les clients avec service account activé
        if not client.get("serviceAccountsEnabled"):
            continue

        client_uuid = client["id"]
        client_id = client.get("clientId")

        # Récupère l'utilisateur du service account pour ce client
        try:
            sa_user = kc.get_client_service_account_user(client_uuid)
            user_id = sa_user.get("id")
        except Exception:
            continue

        if not user_id:
            continue

        # Récupère les realm-roles de ce service-account
        user_realm_roles = [r["name"] for r in kc.get_realm_roles_of_user(user_id)]
        if role_name in user_realm_roles:
            matching_clients.append({"clientId": client_id, "clientUuid": client_uuid})

    logger.info(f"Found {len(matching_clients)} clients with realm role '{role_name}'")
    logger.info(f"Clients: {matching_clients}")
    return matching_clients
    
def reset_password(new_password: str, username: str, email: str) -> JSONResponse:
    """
    Réinitialise le mot de passe d'un utilisateur dans Keycloak.
    
    Args:
        password (str): Le nouveau mot de passe.
        username (str): Le nom d'utilisateur de l'utilisateur dont le mot de passe doit être réinitialisé.
        
    Returns:
        JSONResponse: La réponse de l'API Keycloak.
    """
    kc = get_keycloak_admin(client="pastec_server")
    
    try:
        
        logger.info(f"Resetting password for user {username} with email {email}")
        users = kc.get_users({})
        logger.info(f"Found {len(users)} users in Keycloak")
        logger.info(f"Users: {users}")
        user_id = kc.get_user_id(username)
        kc.set_user_password(user_id, new_password, temporary=False)
        logger.info(f"Password for user {username} reset successfully")
        
        return JSONResponse(status_code=200, content={"message": f"Password for user {username} reset successfully"})
        
    except Exception as e:
        logger.error(f"Failed to reset password for user {username}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

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
            
            logger.info(f"Searching roles for client: {client_name} ({client_id})")
            
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
        
    async def register_new_model(self, model_name: str, description: Optional[str], h5_file: Optional[bytes], py_file: Optional[bytes]) -> JSONResponse:
        """Enregistrer un nouveau modèle dans Keycloak"""
        try:
            token = await self.get_admin_token()
            
            ## creation of a new client for the model
            url = f"{self.keycloak_url}/admin/realms/{self.realm}/clients"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            body = {
                "name": model_name,
                "description": description or "No description provided",
                "clientId": model_name,
                "clientAuthenticatorType": "client-jwt",
                "enabled": True,
                "protocol": "openid-connect",
                "serviceAccountsEnabled": True,
                "publicClient": False,
                "consentRequired": False,
                "standardFlowEnabled": False,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False,
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=body)
                logger.debug(f"Client creation response status: {response.status_code}")
                logger.debug(f"Client creation response headers: {dict(response.headers)}")
                if response.status_code != 201:
                    logger.error(f"Failed to create client: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return JSONResponse(status_code=500, content={"error": "Failed to create client"})
                return JSONResponse(status_code=201, content={"message": "Client created successfully"})
                    
        except HTTPException as e:
            logger.error(f"Failed to get admin token: {str(e)}")
            return JSONResponse(status_code=500, content={"error": "Failed to get admin token"})
        
    async def get_client_rep(self, client_id: str):
        """Obtenir la représentation d'un client"""
        try:
            token = await self.get_admin_token()
            url = f"{self.keycloak_url}/admin/realms/{self.realm}/clients/{client_id}"
            headers = {"Authorization": f"Bearer {token}"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"Failed to get client representation: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return None
                
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting client representation: {str(e)}", exc_info=True)
            return None
        