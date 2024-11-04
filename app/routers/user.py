from fastapi import APIRouter, Depends
from typing import Annotated
from schemas import User
from auth import get_user_info


router = APIRouter()


@router.get("/roles")
def user_roles(user: Annotated[User, Depends(get_user_info)]):
    return {'realm_roles': user.realm_roles,
            'client_roles': user.client_roles}
