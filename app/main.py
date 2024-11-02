"""
Main app file 

JD 31/10/24

"""
from fastapi import FastAPI,Depends
from schemas import User
from auth import get_user_info
from typing import Annotated

app = FastAPI(
    title='PASTEC Server',
    description='Pastec - server backend. This server collects and stores EGMs and annotations.',
    version='0.1',
    swagger_ui_init_oauth={
        'usePkceWithAuthorizationCodeGrant': True,
        'clientId': "pastec_server",
    })

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/secure")
async def root(user: User = Depends(get_user_info)):
    return user.model_dump()

