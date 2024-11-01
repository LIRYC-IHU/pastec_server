from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.main import keycloak
from typing import Optional


router = APIRouter('users')


@router.get("/")
def list_users(type: Optional[str] = None, user = Depends(keycloak.get_current_user)):
    users = keycloak.get_all_users()
    return JSONResponse([u.model_dump for u in users])
