from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from schemas import User
from fastapi import Form
from auth import get_user_info, get_token_with_credentials, get_refresh_token


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

