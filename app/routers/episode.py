"""
Episodes router
Contains most of the important routes of the application

JD 31/10/24
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, Body, Form, File, Query
from fastapi.responses import JSONResponse, FileResponse
from auth import get_user_info, get_auth_info, check_role, get_ai_model_info
import httpx
from schemas import User, AIJob, EpisodeInfo  # Importer EpisodeInfo depuis schemas
from db import engine, Episode, Annotation, Job, JobStatus, Manufacturer, UserType, client  # Importer le client MongoDB existant
from typing import List, Annotated, Dict, Optional
from odmantic import ObjectId
from services.diagnosis_service import DiagnosisService
from services.keycloak_service import KeycloakService
import logging
from bson.binary import Binary
from datetime import datetime
from settings import AI_WORKER_URL
import os
from starlette.background import BackgroundTask

# Configuration du logging (à ajouter au début du fichier)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Router principal pour les épisodes
episode_router = APIRouter(
    prefix="/episode",
    tags=["Episode Management"]
)

# Router pour les EGMs
egm_router = APIRouter(
    prefix="/episode",
    tags=["EGM Management"]
)

# Router pour les annotations
annotation_router = APIRouter(
    prefix="/episode",
    tags=["Annotation Management"]
)

''' Routes for episode handling '''

@episode_router.get("/search")
async def search(
    episode_id: Optional[str] = Query(None),
    episode_type: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    """
    Recherche des épisodes en fonction de plusieurs critères avec pagination
    """
    try:
        query = {}

        # Recherche dans les champs principaux
        if episode_id:
            query["episode_id"] = {"$regex": episode_id, "$options": "i"}
        if episode_type:
            query["episode_type"] = {"$regex": episode_type, "$options": "i"}
        if manufacturer:
            query["manufacturer"] = {"$regex": manufacturer, "$options": "i"}
        
        # Recherche dans les annotations
        if label:
            query["annotations.label"] = {"$regex": label, "$options": "i"}
        if user:
            query["annotations.user"] = {"$regex": user, "$options": "i"}

        # Pagination
        skip = (page - 1) * limit
        cursor = engine.get_collection(Episode).find(query).skip(skip).limit(limit)
        results = await cursor.to_list(length=limit)
        # Convertir les résultats pour JSON
        def convert_document(doc):
            doc["_id"] = str(doc["_id"])  # Convert ObjectId en chaîne
            if "egm" in doc:  # Supprimer ou transformer les données binaires
                doc["egm"] = "Binary data omitted"
            for annotation in doc.get("annotations", []):
                if "_id" in annotation:
                    annotation["_id"] = str(annotation["_id"])
            return doc

        json_results = [convert_document(result) for result in results]
        total = await engine.get_collection(Episode).count_documents(query)

        return JSONResponse(
            status_code=200,
            content={
                "results": json_results,
                "total": total,
                "page": page,
                "limit": limit
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche : {str(e)}")
        raise HTTPException(status_code=500, detail="Error searching episodes")
    
async def send_to_ai(manufacturer: str, episode_type: str, episode_id: str, jobs: List[str]):
    keycloak_service = KeycloakService()
    ai_client_list = await keycloak_service.get_ai_clients(manufacturer, episode_type)
    ai_clients = []
    for ai_client in ai_client_list:
        roles = await keycloak_service.get_ai_client_roles(ai_client)
        logger.info(f"Rôles trouvés pour {ai_client['client_name']}: {roles}")
        if f"{manufacturer.lower()}.{episode_type}" in roles.get(ai_client['client_name'], []):
            ai_clients.append(ai_client['client_name'])

    ai_available = len(ai_clients) > 0
    
    logger.info(ai_available)
    
    if ai_available:
        logger.info(f"Modèles IA disponibles: {ai_clients}")
        logger.info("Envoi des requêtes vers le serveur IA")
        for ai_client in ai_clients:
            job_id = str(ObjectId())
            jobs.append(job_id)
            logger.info(f"Envoi de la requête au serveur IA pour le modèle {ai_client} avec job_id: {job_id}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{AI_WORKER_URL}/process/{job_id}",
                    json={
                        "id_model": ai_client,
                        "job_id": job_id
                    }
                )
                logger.info(f"Requête envoyée à l'IA {ai_client}: {response.status_code}")
                if response.status_code == 202:
                    logger.info(f"Requête acceptée par l'IA {ai_client}, stockage du job ID dans mongodb sous la collection jobs")
                    await engine.save(Job(
                        job_id=job_id,
                        episode_id=episode_id,
                        id_model=ai_client,
                        status=JobStatus.PENDING,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        annotation=None,
                        confidence=None,
                        details=None
                    ))
                else:
                    logger.error(f"Erreur lors de l'envoi à l'IA {ai_client}: {response.text}")
    return ai_clients, ai_available

@episode_router.post("/upload_episode")
async def upload_episode(
    auth_info: dict = Depends(get_auth_info),
    patient_id: str = Form(...),
    manufacturer: str = Form(...),
    episode_type: str = Form(...),
    age_at_episode: int = Form(...),
    episode_duration: str = Form(...),  # Correction du type de episode_duration
    episode_id: str = Form(...)
) -> JSONResponse:
    try:
        jobs = []
        # Vérifier si l'épisode existe déjà
        existing_episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        
        if existing_episode:
            logger.info(f"Episode {episode_id} déjà existant")
            diagnosis_service = DiagnosisService(engine)
            labels = await diagnosis_service.get_possible_labels(
                manufacturer=existing_episode.manufacturer,
                episode_type=existing_episode.episode_type
            )
            ai_clients, ai_available = await send_to_ai(manufacturer, episode_type, episode_id, jobs)
            return JSONResponse(
                status_code=200,
                content={
                    "episode_id": existing_episode.episode_id,
                    "patient_id": existing_episode.patient_id,
                    "manufacturer": existing_episode.manufacturer,
                    "episode_type": existing_episode.episode_type,
                    "labels": labels,
                    "exists": True,
                    "annotated": True if existing_episode.annotations else False,
                    "ai_available": ai_available,
                    "ai_clients": ai_clients if ai_available else [],
                    "jobs": jobs if jobs else []
                }
            )

        # Si l'épisode n'existe pas, continuer avec la création
        manufacturer_enum = Manufacturer(manufacturer.lower())
        episode = Episode(
            episode_id=episode_id,
            patient_id=patient_id,
            manufacturer=manufacturer_enum,
            episode_type=episode_type,
            age_at_episode=age_at_episode,
            episode_duration=episode_duration,
            annotations=[]
        )
        
        await engine.save(episode)
        logger.info("Nouvel épisode créé et sauvegardé")
        
        diagnosis_service = DiagnosisService(engine)
        labels = await diagnosis_service.get_possible_labels(
            manufacturer=episode.manufacturer,
            episode_type=episode.episode_type
        )
        
        return JSONResponse(
            status_code=201,
            content={
                "episode_id": episode.episode_id,
                "patient_id": episode.patient_id,
                "manufacturer": episode.manufacturer,
                "episode_type": episode.episode_type,
                "labels": labels,
                "exists": False,
                "annotated": False
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'upload: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(status_code=422, detail=str(e))
    

@episode_router.get("/{id}")
async def get_episode_by_id(id: ObjectId, auth_info: dict = Depends(get_auth_info)) -> EpisodeInfo:
    logger.info(f"Requête reçue pour obtenir l'épisode avec id: {id} et auth_info: {auth_info}")
    """ 
    Get info about a given episode from its `id`
    """
    
    
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    return EpisodeInfo(**episode.model_dump())


@episode_router.delete("/{id}")
async def delete_episode_by_id(id: ObjectId, auth_info: dict = Depends(get_auth_info)) -> EpisodeInfo:
    logger.info(f"Requête reçue pour supprimer l'épisode avec id: {id} et auth_info: {auth_info}")
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    await engine.delete(episode)
    return EpisodeInfo(**episode.model_dump())

""" 
Routes for EGM handling
"""

@egm_router.get("/{episode_id}/egm")
async def get_episode_egm(
    episode_id: str, 
    auth_info: dict = Depends(get_auth_info) 
    ) -> FileResponse:
    logger.info(f"Requête reçue pour obtenir l'EGM avec episode_id: {episode_id} et auth_info: {auth_info}")
    """
    Récupère l'EGM d'un épisode spécifique
    
    Parameters:
    - episode_id: Identifiant unique de l'épisode
    - user: Utilisateur authentifié (injecté automatiquement)
    
    Returns:
    - FileResponse contenant l'EGM
    """
    
    logger.info(f"Requête reçue par {auth_info['type']}: {auth_info['info']}")
    
    try:
        # Rechercher l'épisode par son ID
        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            raise HTTPException(404, detail='No episode with this ID.')
        
        # Vérifier si l'EGM existe
        if not hasattr(episode, 'egm') or not episode.egm:
            raise HTTPException(404, detail='No EGM stored for this episode.')
        
        # Créer un fichier temporaire pour stocker l'EGM
        temp_file = f"/tmp/{episode_id}.svg"
        with open(temp_file, "wb") as f:
            if isinstance(episode.egm, Binary):
                f.write(episode.egm)
            else:
                # Si l'EGM est stocké en base64
                import base64
                f.write(base64.b64decode(episode.egm))
        
        # Retourner le fichier
        return FileResponse(
            path=temp_file,
            filename=f"episode_{episode_id}.svg",
            media_type="image/svg+xml",
            background=BackgroundTask(lambda: os.remove(temp_file))
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'EGM: {str(e)}")
        raise HTTPException(500, detail=str(e))


@egm_router.post("/{episode_id}/egm", status_code=201)
async def post_episode_egm(
    user: Annotated[User, Depends(get_user_info)],
    episode_id: str,
    file: UploadFile = File(...)
):
    logger.info(f"Tentative d'upload EGM pour l'épisode {episode_id} par l'utilisateur {user.username}")
    logger.info(f"Tentative d'upload EGM pour l'épisode {episode_id}")
    logger.info(f"Fichier reçu: {file.filename}")
    logger.info(f"Content type: {file.content_type}")
    logger.info(f"Headers: {file.headers}")
    
    try:
        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            logger.error(f"Episode {episode_id} non trouvé")
            raise HTTPException(404, detail='No episode with this ID.')
        
        try:
            # Lire le contenu du fichier avec gestion explicite des erreurs
            content = b""
            chunk_size = 1024 * 1024  # 1MB chunks
            while chunk := await file.read(chunk_size):
                content += chunk
                logger.info(f"Lu {len(chunk)} bytes")
            
            logger.info(f"Taille totale du fichier: {len(content)} bytes")
            
            if len(content) == 0:
                raise HTTPException(400, detail="Empty file received")
            
            # Stocker l'EGM dans l'épisode
            episode.egm = Binary(content)
            await engine.save(episode)
            jobs = []
            ai_clients, ai_available = await send_to_ai(episode.manufacturer, episode.episode_type, episode_id, jobs)
            
            logger.info(f"EGM sauvegardé avec succès pour l'épisode {episode_id}")
            
            return JSONResponse(
                status_code=201,
                content={
                    "message": "EGM stored successfully",
                    "ai_available": ai_available,
                    "ai_clients": ai_clients if ai_available else [],
                    "jobs": jobs if jobs else []}
            )

        except Exception as read_error:
            logger.error(f"Erreur lors de la lecture du fichier: {str(read_error)}")
            logger.exception("Traceback de l'erreur de lecture:")
            raise HTTPException(400, detail=f"Error reading file: {str(read_error)}")
            
    except ValueError as e:
        logger.error(f"Erreur de format d'ID: {str(e)}")
        raise HTTPException(400, detail=f"Invalid episode ID format: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur lors de l'upload de l'EGM: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(500, detail=f"Error storing EGM: {str(e)}")

''' Routes for annotation updates '''

@annotation_router.put("/{episode_id}/annotation")
async def put_episode_annotation(
    episode_id: str,
    auth_info: dict = Depends(get_auth_info),
    label: str = Body(..., embed=True),
    details: Optional[Dict] = Body(None)
) -> JSONResponse:
    logger.info(f"Tentative d'ajout d'annotation pour l'épisode {episode_id} par {auth_info['type']}: {auth_info['info']}")
    """Ajoute une annotation à un épisode"""
    logger.info(f"Tentative d'ajout d'annotation pour l'épisode {episode_id}")
    logger.info(f"Label reçu: {label}")
    logger.info(f"Détails reçus: {details}")
    
    try:
        # Rechercher par episode_id
        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            logger.error(f"Episode {episode_id} non trouvé")
            raise HTTPException(404, detail='No episode with this ID.')
        
        # Créer la nouvelle annotation avec le bon type d'utilisateur
        if auth_info['type'] == 'user':
            user = auth_info['info']
            new_annotation = Annotation(
                user=user.username,
                user_type=UserType.MD,  # ou choisir le type approprié selon votre logique
                label=label,
                details=details  # Champ optionnel
            )
        else:
            ai_model = auth_info['info']
            new_annotation = Annotation(
                user=ai_model.client_id,
                user_type=UserType.AI,
                label=label,
                details=details
            )
        
        
        # Ajouter l'annotation à la liste des annotations de l'épisode
        episode.annotations.append(new_annotation)
        await engine.save(episode)
        
        logger.info(f"Annotation ajoutée avec succès pour l'épisode {episode_id}")
        return JSONResponse(
            status_code=200,
            content={
                "message": "Annotation added successfully",
                "episode_id": episode_id,
                "annotation": {
                    "user": new_annotation.user,
                    "user_type": new_annotation.user_type,
                    "label": new_annotation.label,
                    "details": new_annotation.details
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'annotation: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(500, detail=f"Error adding annotation: {str(e)}")