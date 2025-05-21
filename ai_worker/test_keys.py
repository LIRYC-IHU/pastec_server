import os, asyncio
from auth import get_access_token, fetch_egm
from fastapi import APIRouter, HTTPException

router = APIRouter()

async def e2e() -> bytes:
    jwt_token = await get_access_token("ai_bio_af", "./private_keys/", "ai_bio_af")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    
            # Créer un fichier temporaire pour stocker l'EGM

    egm_bytes = await fetch_egm("228b261f2b57f9246258a0a3690e7128bf907cad811fe32795dfac654c139437", headers)
    open("/tmp/egm.svg", "wb").write(egm_bytes)
    print("👍 EGM reçu !")
    return egm_bytes
