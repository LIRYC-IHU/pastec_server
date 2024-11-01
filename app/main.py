"""
Main app file 

JD 31/10/24
"""
from fastapi import FastAPI, Depends
from pymongo import MongoClient
from fastapi_keycloak import FastAPIKeycloak
from app.routers import episode, users
from app.settings import *


# Mongo DB client
mongo_client = MongoClient(MONGODB_URI)

# Keycloak client
keycloak = FastAPIKeycloak(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    client_secret=KEYCLOAK_CLIENT_SECRET,
    admin_client_secret=KEYCLOAK_CLIENT_SECRET,
    realm=KEYCLOAK_REALM,
    callback_uri="http://localhost:8000/callback"
)

# FastAPI app
app = FastAPI()
app.add_middleware(keycloak.middleware())

app.include_router(users.router)
app.include_router(episode.router)

@app.get("/protected")
def protected_route(user=Depends(keycloak.get_current_user)):
    return {"message": f"Hello, {user.username}"}

@app.get("/unprotected")
def unprotected_route():
    return {"message": "Hello, World!"}
