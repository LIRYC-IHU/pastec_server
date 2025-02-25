from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from schemas import User, Token
from fastapi import Form, Header
from services.keycloak_service import KeycloakService
import httpx
import logging
from fastapi.responses import HTMLResponse
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
    
@user_router.get('/privacy', response_class = HTMLResponse)
async def privacy_policy() -> HTMLResponse:
    return """
    <html>
    <head>
    <meta charset="utf-8">
    <title>Politique de Confidentialité</title>
    <style>
        body {
        font-family: Arial, sans-serif;
        margin: 2em;
        line-height: 1.6;
        }
        h1, h2, h3 {
        color: #333;
        }
        h1 {
        margin-bottom: 0.5em;
        }
        p {
        margin-bottom: 1em;
        }
    </style>
    </head>

    <body>
    <h1>Politique de Confidentialité</h1>
    <p><em>Dernière mise à jour : 25/02/2025</em></p>

    <h2>1. Introduction</h2>
    <p>Cette Politique de Confidentialité décrit la manière dont l’extension <strong>PASTEC Plugin</strong> collecte, utilise et protège les informations des utilisateurs lorsqu’ils installent et utilisent l’Extension sur le navigateur Google Chrome. Votre utilisation de l’Extension implique votre acceptation de cette Politique de Confidentialité.</p>

    <h2>2. Données collectées</h2>

    <h3>2.1 Données de navigation / Scraping</h3>
    <p>L’Extension peut lire et extraire (“scraper”) certaines informations présentes sur les pages web que vous visitez, uniquement lorsque vous y autorisez l’injection d’un script, par exemple via un clic explicite ou selon une configuration déterminée. Les types de données potentiellement collectés incluent du contenu textuel, des tableaux ou des images affichées publiquement. Aucune donnée sensible (mots de passe, informations bancaires, etc.) n’est collectée ; si de tels champs sont détectés, ils sont ignorés ou anonymisés.</p>

    <h3>2.2 Données d’authentification et cookies</h3>
    <p>Pour automatiser la connexion à certains sites, l’Extension peut manipuler ou lire les cookies liés à votre session. Les identifiants (login/mot de passe) ne sont collectés qu’avec votre consentement et restent stockés sur votre appareil (via <code>chrome.storage</code> ou un équivalent). Nous ne transmettons pas vos informations d’authentification à des serveurs tiers.</p>

    <h3>2.3 Stockage local</h3>
    <p>L’Extension utilise l’API <code>chrome.storage</code> pour mémoriser vos préférences (paramètres, configuration utilisateur, résultats temporaires d’analyse). Ces données sont stockées localement et ne sont pas envoyées à notre serveur, sauf mention contraire.</p>

    <h2>3. Utilisation des données</h2>
    <p>Les données collectées (contenu scrapé, cookies, identifiants) servent exclusivement à automatiser et faciliter votre navigation, ou à extraire des informations à votre demande, afin d’améliorer votre expérience sur les sites compatibles. Nous n’exploitons pas ces données à des fins commerciales ni publicitaires, et nous ne les revendons pas à des tiers.</p>

    <h2>4. Partage des données</h2>
    <p>Nous ne communiquons pas vos données à des tiers, sauf obligation légale ou consentement explicite de votre part (par exemple, si vous décidez de synchroniser vos informations via un service en ligne). Si les autorités légales nous en font la demande, nous pourrons être amenés à divulguer certaines informations, mais nous vous en informerons dans la mesure du possible.</p>

    <h2>5. Sécurité</h2>
    <p>Nous mettons en œuvre des mesures techniques et organisationnelles pour protéger vos données contre tout accès non autorisé ou modification illégitime. Toutefois, aucun système n’est infaillible et nous ne pouvons garantir une sécurité absolue.</p>

    <h2>6. Droits de l’utilisateur</h2>
    <p>Vous pouvez désinstaller l’Extension à tout moment via la page “Extensions” de Chrome, ce qui supprime la possibilité pour l’Extension d’accéder à vos pages web. Vous pouvez également supprimer ou réinitialiser les données stockées localement. Si vous résidez dans l’Union Européenne ou une zone à législation similaire, vous bénéficiez peut-être de droits d’accès, de rectification ou de suppression concernant vos données personnelles.</p>

    <h2>7. Mineurs</h2>
    <p>L’Extension n’est pas destinée aux enfants de moins de 16 ans. Nous ne collectons pas sciemment d’informations auprès de mineurs.</p>

    <h2>8. Modifications de la Politique</h2>
    <p>Nous pouvons mettre à jour cette Politique de Confidentialité pour refléter les évolutions de l’Extension ou les changements de la législation. En cas de modification substantielle, nous vous en informerons via les notes de version de l’Extension ou un moyen de communication approprié.</p>

    <h2>9. Contact</h2>
    <p>Pour toute question à propos de cette Politique de Confidentialité, veuillez nous contacter à l’adresse : <strong>pastec@ihu-liryc.fr</strong>.</p>

    <p>Merci d’utiliser <strong>PASTEC Plugin</strong>.</p>
    </body>
    </html>"""
