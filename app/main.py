"""
Main app file 

JD 31/10/24

"""
from fastapi import FastAPI,Depends
from schemas import User
from auth import get_user_info
from typing import Annotated
from routers import episode, user
from contextlib import asynccontextmanager


app = FastAPI(
    title='PASTEC Server',
    description='Pastec - server backend. This server collects and stores EGMs and annotations.',
    version='0.1',
    swagger_ui_init_oauth={
        'usePkceWithAuthorizationCodeGrant': True,
        'clientId': "pastec_server",
    })

# Routers for users & episode management
app.include_router(user.router, prefix='/user', tags=['User management'])
app.include_router(episode.router, prefix='/episode', tags=['Episode management'])

# Example public route
@app.get("/")
async def root():
    return {"message": "Hello World"}

# Example secure route
@app.get("/secure")
async def root(user: Annotated[User, Depends(get_user_info)]):
    return user.model_dump()


