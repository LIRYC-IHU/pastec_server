from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from keycloak import keycloak
from typing import Optional


router = APIRouter('users')


@router.get("/admin")
def admin(user = Depends(keycloak.get_current_user(required_roles=["admin"]))):
    return f'Hi premium user {user}'

@router.get("/roles")
def user_roles(user = Depends(keycloak.get_current_user)):
    return f'{user.roles}'

@router.get("/")
def list_users(type: Optional[str] = None, user = Depends(keycloak.get_current_user)):
    users = keycloak.get_all_users()
    return JSONResponse([u.model_dump for u in users])
