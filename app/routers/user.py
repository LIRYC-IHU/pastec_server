import json

from fastapi import APIRouter, Depends, HTTPException, Response
from typing import Annotated
from db import Center, UserType, UserEntry, User
from fastapi import Form
from fastapi.responses import PlainTextResponse
from services.config_bundle_service import build_signed_center_bundle, get_public_key_pem
from services.pepper_service import create_center_pepper
from services.keycloak_service import create_new_user, reset_password
import logging
from fastapi.responses import HTMLResponse, JSONResponse
from auth import build_user_from_payload, check_authorization, decode_token, get_refresh_token
import os
from keycloak import KeycloakOpenID

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
def user_roles(user: Annotated[User, Depends(check_authorization())]):
    return {
        "realm_roles": user.realm_roles,
        "client_roles": user.client_roles,
        "roles": user.roles,
        "centers": user.centers,
        "projects": user.projects,
        "primary_center": user.primary_center,
        "user_type": user.user_type,
    }


@user_router.get("/me/access")
def my_access(user: Annotated[User, Depends(check_authorization())]):
    return user.model_dump()


@user_router.post("/centers/{center}/pepper")
async def create_pepper_for_center(
    center: str,
    api_url: str | None = None,
    rights: User = Depends(check_authorization("pastec-admin"))
) -> Response:
    record, pepper = await create_center_pepper(center=center, created_by=rights.username)
    bundle = build_signed_center_bundle(
        center=record.center,
        pepper=pepper,
        api_url=api_url,
        created_by=rights.username,
    )
    bundle_filename = f"pastec-center-{record.center}-bundle.json"
    return Response(
        content=json.dumps(bundle, sort_keys=True, indent=2),
        media_type="application/json",
        status_code=201,
        headers={
            "Content-Disposition": f'attachment; filename="{bundle_filename}"',
            "X-PASTEC-Center": record.center,
            "X-PASTEC-Pepper-Hash": record.pepper_hash,
        },
    )


@user_router.get("/config-bundle/public-key", response_class=PlainTextResponse)
async def get_config_bundle_public_key() -> str:
    return get_public_key_pem()

    
# Exemple d'utilisation dans une route
@user_router.post("/login")
async def login(
    username: Annotated[str, Form()], 
    password: Annotated[str, Form()]
    ) -> str:

    # Configure client
    # For versions older than 18 /auth/ must be added at the end of the server_url.
    keycloak_openid = KeycloakOpenID(server_url=os.getenv("KEYCLOAK_INTERNAL_SERVER_URL"),
                                    client_id=os.getenv("KEYCLOAK_CLIENT_ID"),
                                    realm_name=os.getenv("KEYCLOAK_REALM"),
                                    verify=True)
    
    # Authenticate user
    try:
        token = keycloak_openid.token(username, password)
        payload = await decode_token(token["access_token"])
        user = build_user_from_payload(payload)
        logger.info(f"User {username} authenticated successfully.")
        return JSONResponse (
            content={
                "access_token": token["access_token"],
                "token_type": "bearer",
                "refresh_token": token["refresh_token"],
                "expires_in": token["expires_in"],
                "user": user.model_dump(),
            },
            status_code=200
        )
    except Exception as e:
        logger.error(f"Authentication failed for user {username}: {e}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    
    
    
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
        payload = await decode_token(token)
        user = build_user_from_payload(payload)
        return {
            "valid": True,
            "user": user.model_dump(),
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        return {"valid": False, "message": str(e)}
    
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

@user_router.get('/callback', response_class = HTMLResponse)
async def callback() -> HTMLResponse:
        return """
    <html>
    <head>
    <meta charset="utf-8">
    <title>Authentification - PASTEC</title>
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
    <h1>Authentification réussie</h1>
    <p>Vous pouvez maintenant fermer cette fenêtre et retourner à l'application.</p>
    </body>
    </html>"""
    
@user_router.post('/new-user')
async def create_user(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    email: Annotated[str, Form()],
    first_name: Annotated[str, Form()],
    last_name: Annotated[str, Form()],
    center: Annotated[Center, Form()],
    user_type: Annotated[UserType, Form()],
    rights: User = Depends(check_authorization("pastec-admin"))
) -> JSONResponse:
    
    user_entry = UserEntry(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        center=center,
        user_type=user_type
    )
    response = await create_new_user(user_entry)
    
    return response

@user_router.post('/reset-password')
def reset_pwd(
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    new_password: Annotated[str, Form()]
) -> JSONResponse:
    return reset_password(
        username=username,
        email=email,
        new_password=new_password
    )
