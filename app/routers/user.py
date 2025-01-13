from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from schemas import User, Token
from fastapi import Form, Header
from services.keycloak_service import KeycloakService
import httpx
import logging
from auth import get_user_info, get_token_with_credentials, get_refresh_token
from settings import KEYCLOAK_CLIENT_ID, KEYCLOAK_INTERNAL_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID 

KEYCLOAK_INTROSPECT_URL = f"{KEYCLOAK_INTERNAL_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

user_router = APIRouter(
    prefix="/users",
    tags=["User Management"]
)

@user_router.get("/roles")
def user_roles(user: Annotated[User, Depends(get_user_info)]):
    return {'realm_roles': user.realm_roles,
            'client_roles': user.client_roles}
    
# Exemple d'utilisation dans une route
@user_router.post("/login")
async def login(
    username: Annotated[str, Form()], 
    password: Annotated[str, Form()]
    ):
    token = await get_token_with_credentials(username, password)
    return {
        "access_token": token["access_token"],
        "token_type": "bearer",
        "refresh_token": token["refresh_token"]
    }

@user_router.post("/token/refresh")
async def refresh_token(refresh_token: Annotated[str, Form()]):
    try:
        print(f"Received refresh_token: {refresh_token}")  # Debug log

        # Vérification de la présence et de la validité du token
        if not refresh_token or len(refresh_token.split(".")) != 3:
            raise HTTPException(status_code=400, detail="Invalid refresh token format")

        new_token = await get_refresh_token(refresh_token=refresh_token)

        return {
            "access_token": new_token["access_token"],
            "token_type": "bearer",
            "refresh_token": new_token["refresh_token"],
            "expires_in": new_token["expires_in"]
        }
    except Exception as e:
        print(f"Error during token refresh: {e}")  # Debug log
        raise HTTPException(status_code=400, detail="Failed to refresh token")
    
@user_router.post("/validate-token")
async def validate_token(token: Annotated[str, Form()]):
    """
    Validate a token using the Keycloak introspect endpoint.

    Parameters:
    - token: The token to validate.

    Returns:
    - JSON response with token validity and details.
    """
    try:
        keycloak_service = KeycloakService()
        
        # Keycloak introspect URL
        introspect_url = f"{keycloak_service.keycloak_url}/realms/{keycloak_service.realm}/protocol/openid-connect/token/introspect"
        logger.info(f"Keycloak introspect URL: {introspect_url}")

        # Payload for introspection
        payload = {
            "token": token,
            "client_id": keycloak_service.client_id,
            "client_secret": keycloak_service.client_secret
        }
        logger.info(f"Payload being sent to Keycloak: {payload}")

        # Sending request to Keycloak
        logger.info("Sending request to Keycloak introspect endpoint...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(introspect_url, data=payload)
        
        # Handling response
        logger.info(f"Received response from Keycloak with status code: {response.status_code}")
        if response.status_code != 200:
            logger.error("Error communicating with Keycloak.")
            logger.error(f"Response body: {response.text}")
            raise HTTPException(status_code=403, detail="Error communicating with Keycloak")
        
        # Parse response
        token_data = response.json()
        logger.info(f"Token introspection response: {token_data}")

        # Check token validity
        if not token_data.get("active", False):
            logger.warning("Token is not active.")
            return {"valid": False, "message": "Token is invalid or expired"}
        
        logger.info("Token is valid.")
        return {
            "valid": True,
            "token_data": token_data
        }
    except httpx.RequestError as e:
        logger.error(f"HTTP Request to Keycloak failed: {str(e)}")
        raise HTTPException(500, f"Failed to connect to Keycloak: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        raise HTTPException(500, f"Unexpected error: {str(e)}")