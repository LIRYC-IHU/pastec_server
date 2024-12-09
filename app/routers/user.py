from fastapi import APIRouter, Depends
from typing import Annotated
from schemas import User
from fastapi import Form
from auth import get_user_info, get_token_with_credentials
from fastapi import Form
from auth import get_user_info, get_token_with_credentials


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

