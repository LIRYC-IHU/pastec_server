import os, asyncio
from auth import get_access_token, fetch_egm
from fastapi import APIRouter, HTTPException
from keycloak import KeycloakOpenID
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

async def e2e(client_id) -> bytes:

    jwt_token = await get_access_token(client_id, f'./private_keys/ai_{client_id}.pem', lifetime=300)    
    
    logger.info(f"JWT Token: {jwt_token}")
    
    headers = {"Authorization": f"Bearer {jwt_token}"}

    egm_bytes = await fetch_egm("228b261f2b57f9246258a0a3690e7128bf907cad811fe32795dfac654c139437", headers)
    
    open("/tmp/egm.svg", "wb").write(egm_bytes)
    print("👍 EGM reçu !")
    return egm_bytes
