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
from fastapi.middleware.cors import CORSMiddleware
import json
from motor.motor_asyncio import AsyncIOMotorClient
from db import DiagnosesCollection
import logging
from settings import MONGODB_URI, MONGODB_DB_NAME

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Vérifier la connexion MongoDB
        await engine.admin.command('ping')
        logger.info("Connexion MongoDB établie")
        await init_diagnoses(engine)
    except Exception as e:
        logger.error(f"Erreur de connexion MongoDB: {str(e)}")
        # On continue quand même le démarrage de l'application
    yield

app = FastAPI(
    lifespan=lifespan,
    title='PASTEC Server',
    description='Pastec - server backend. This server collects and stores EGMs and annotations.',
    version='0.1',
    swagger_ui_init_oauth={
        'usePkceWithAuthorizationCodeGrant': True,
        'clientId': "pastec_server",
        'redirect_uri': 'http://localhost:8000/docs/oauth2-redirect'
    })

# Configuration des origines autorisées
origins = [
    "https://www.latitudenxt.bostonscientific-international.com",
    "http://localhost:8000",  # Pour le développement local
    "http://127.0.0.1:8000",  # Pour le développement local
]

# Ajout du middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes HTTP
    allow_headers=["*"],  # Autorise tous les headers
)

# Routers for users & episode management
app.include_router(user.router, prefix='/users', tags=['User management'])
app.include_router(episode.router, prefix='/episode', tags=['Episode management'])

# Example public route
@app.get("/")
async def root():
    return {"message": "Hello World"}

# Example secure route
@app.get("/secure")
async def root(user: Annotated[User, Depends(get_user_info)]):
    return user.model_dump()

# Initialisation de la base de données
async def init_diagnoses(engine: AsyncIOMotorClient):
    try:
        db = engine.get_database(MONGODB_DB_NAME)
        collection = db.get_collection('diagnoses')
        
        existing = await collection.find_one({})
        
        if not existing:
            logger.info("Initialisation des diagnostics dans la base de données...")
            try:
                with open('app/diagnosis-maps.json', 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                # Le JSON est déjà dans le bon format, pas besoin de transformation
                diagnoses = {"manufacturer_diagnoses": raw_data}
                await collection.insert_one(diagnoses)
                logger.info("Diagnostics initialisés avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation des diagnostics: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation des diagnostics: {str(e)}")

# Créer une instance du client MongoDB avec des paramètres de timeout
engine = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000
)


