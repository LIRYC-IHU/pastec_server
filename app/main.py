"""
Main app file 

JD 31/10/24

"""
from fastapi import FastAPI,Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from schemas import User
from db import Episode
from auth import get_user_info
from typing import Annotated
from routers.episode import episode_router, egm_router, annotation_router
from routers.ai import ai_router 
from routers.user import user_router
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from motor.motor_asyncio import AsyncIOMotorClient
from db import DiagnosesCollection
import logging
from settings import MONGODB_URI, MONGODB_DB_NAME
 # Importer le routeur IA

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Vérifier la connexion MongoDB
        await engine.admin.command('ping')
        logger.info("Connexion MongoDB établie")
        await init_diagnoses(engine)
        
        # Afficher les informations sur le modèle Episode
        logger.info(f"Structure du modèle Episode: {Episode.__fields__}")
        
        # Vérifier les collections existantes - CORRECTION ICI
        db = engine.get_database(MONGODB_DB_NAME)
        collections = await db.list_collection_names()
        logger.info(f"Collections disponibles: {collections}")
        
        # Afficher les routes
        logger.info("Routes enregistrées:")
        for route in app.routes:
            logger.info(f"{route.path} [{route.methods}]")
            
    except Exception as e:
        logger.error(f"Erreur lors du démarrage: {str(e)}")
        raise e
    yield

app = FastAPI(
    lifespan=lifespan,
    title='PASTEC Server',
    description='Pastec - server backend. This server collects and stores EGMs and annotations.',
    version='0.1',
    swagger_ui_init_oauth={
        'usePkceWithAuthorizationCodeGrant': True,
        'clientId': "pastec_server"
    })

# Configuration des origines autorisées
origins = [
    "https://www.latitudenxt.bostonscientific-international.com",
    "*",
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
    expose_headers=["*"],
    max_age=3600# Expose le header Content-Disposition
)

# Routers for users & episode management
app.include_router(user_router)
app.include_router(episode_router)
app.include_router(egm_router)
app.include_router(annotation_router)
app.include_router(ai_router)  # Inclure le routeur IA

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
        
        logger.info("Vérification de l'existence des diagnostics...")
        existing = await collection.find_one({})
        
        if not existing:
            logger.info("Aucun diagnostic trouvé, initialisation nécessaire...")
            try:
                file_path = 'diagnosis-maps.json'
                logger.info(f"Tentative de lecture du fichier: {file_path}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    logger.info(f"Données JSON chargées avec succès. Fabricants trouvés: {list(raw_data.keys())}")
                
                diagnoses = {"manufacturer_diagnoses": raw_data}
                result = await collection.insert_one(diagnoses)
                logger.info(f"Diagnostics insérés avec succès. ID: {result.inserted_id}")
                
                # Vérification de l'insertion
                verification = await collection.find_one({"_id": result.inserted_id})
                if verification:
                    logger.info("Vérification réussie : données correctement insérées")
                else:
                    logger.error("Échec de la vérification : les données n'ont pas été correctement insérées")
                    
            except FileNotFoundError:
                logger.error(f"Fichier non trouvé: {file_path}")
                logger.error(f"Contenu du répertoire actuel: {os.listdir('.')}")
            except json.JSONDecodeError as e:
                logger.error(f"Erreur de décodage JSON: {str(e)}")
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation des diagnostics: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur de connexion à MongoDB: {str(e)}")

# Créer une instance du client MongoDB avec des paramètres de timeout
engine = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000
)

# Ajoutez ce code pour déboguer
@app.on_event("startup")
async def startup_event():
    print("Routes enregistrées :")
    for route in app.routes:
        print(f"{route.path} [{route.methods}]")


