"""
Episodes router
Contains most of the important routes of the application

JD 31/10/24
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, Body, Form, File
from fastapi.responses import JSONResponse, FileResponse
from auth import get_user_info, check_role
from schemas import User
from db import engine, Episode, Annotation, EpisodeInfo, DiagnosesCollection, Manufacturer, UserType
from typing import List, Annotated
from odmantic import ObjectId
from services.diagnosis_service import DiagnosisService
from services.keycloak_service import KeycloakService
import logging
from bson.binary import Binary

# Configuration du logging (à ajouter au début du fichier)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/episodelist")
async def list_episodes(user: Annotated[User, Depends(get_user_info)], 
                        limit: int = 20
                        ) -> List[EpisodeInfo]:
    """
    List all the episodes that we have, potentially matching some criteria 
    """
    # TODO: add filters
    episodes = await engine.find(Episode, limit=limit)
    return [EpisodeInfo(**e.model_dump()) for e in episodes]

#créer une route post pour l'upload d'épisodes de type Episode (cf. db.py), et renvoyer les labels possibles pour le type d'épisode contenu dans la collection diagnoses de la database

@router.post("/upload_episode")
async def upload_episode(
    user: Annotated[User, Depends(get_user_info)],
    patient_id: str = Form(...),
    manufacturer: str = Form(...),
    episode_type: str = Form(...),
    age_at_episode: int = Form(...),
    episode_duration: str = Form(...),
    episode_id: str = Form(...)
) -> JSONResponse:
    logger.info(f"Tentative d'upload avec les paramètres:")
    logger.info(f"episode_id: {episode_id}")
    
    try:
        # Vérifier les utilisateurs IA disponibles
        keycloak_service = KeycloakService()
        ai_users = await keycloak_service.get_ai_users(manufacturer, episode_type)
        ai_available = len(ai_users) > 0
        logger.info(f"IA disponibles: {ai_users if ai_available else 'aucune'}")

        # Vérifier si l'épisode existe déjà
        existing_episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if existing_episode:
            logger.info(f"Episode {episode_id} déjà existant")
            diagnosis_service = DiagnosisService(engine)
            labels = await diagnosis_service.get_possible_labels(
                manufacturer=existing_episode.manufacturer,
                episode_type=existing_episode.episode_type
            )
            return JSONResponse(
                status_code=200,  # 200 au lieu de 201 car pas de création
                content={
                    "episode_id": existing_episode.episode_id,
                    "patient_id": existing_episode.patient_id,
                    "manufacturer": existing_episode.manufacturer,
                    "episode_type": existing_episode.episode_type,
                    "labels": labels,
                    "exists": True,  # Indicateur pour le frontend
                    "ai_available": ai_available,
                    "ai_users": ai_users if ai_available else []
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
                "ai_available": ai_available,
                "ai_users": ai_users if ai_available else []
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'upload: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{id}")
async def get_episode_by_id(id: ObjectId, user: Annotated[User, Depends(get_user_info)]) -> EpisodeInfo:
    """ 
    Get info about a given episode from its `id`
    """
    
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    return EpisodeInfo(**episode.model_dump())


@router.delete("/{id}")
async def delete_episode_by_id(id: ObjectId, user: Annotated[User, Depends(get_user_info)]) -> EpisodeInfo:
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    await engine.delete(episode)
    return EpisodeInfo(**episode.model_dump())


""" 
EPISODE EGM 
"""

@router.get("/{episode_id}/egm")
async def get_episode_egm(episode_id: str, user: Annotated[User, Depends(get_user_info)]) -> FileResponse:
    """ Get egm of the episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    if egm_not_found:
        raise HTTPException(404, detail='No EGM stored for this episode.')
    
    return episode


@router.post("/{episode_id}/egm", status_code=201)
async def post_episode_egm(
    user: Annotated[User, Depends(get_user_info)],
    episode_id: str,
    file: UploadFile = File(...)
):
    """ Store EGM of the episode """
    logger.info(f"Tentative d'upload EGM pour l'épisode {episode_id}")
    logger.info(f"Fichier reçu: {file.filename}")
    logger.info(f"Content type: {file.content_type}")
    logger.info(f"Headers: {file.headers}")
    
    try:
        # Rechercher par episode_id au lieu de _id
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
            logger.info(f"EGM sauvegardé avec succès pour l'épisode {episode_id}")
            
            return JSONResponse(
                status_code=201,
                content={"message": "EGM stored successfully"}
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


@router.post("/{episode_id}/annotation")
def post_episode_label(episode_id: ObjectId, annotation: Annotation, user: Annotated[User, Depends(get_user_info)]) -> str:
    """ Save a new annotation for an episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    return label_id


@router.put("/{episode_id}/annotation")
async def put_episode_annotation(
    user: Annotated[User, Depends(get_user_info)],
    episode_id: str,
    label: str = Body(..., embed=True)
) -> JSONResponse:
    """Ajoute une annotation à un épisode"""
    logger.info(f"Tentative d'ajout d'annotation pour l'épisode {episode_id}")
    logger.info(f"Label reçu: {label}")
    
    try:
        # Rechercher par episode_id
        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            logger.error(f"Episode {episode_id} non trouvé")
            raise HTTPException(404, detail='No episode with this ID.')
        
        # Créer la nouvelle annotation avec le bon type d'utilisateur
        new_annotation = Annotation(
            user=user.username,
            user_type=UserType.MD,  # ou choisir le type approprié selon votre logique
            label=label,
            details={}  # Champ optionnel
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
                    "label": new_annotation.label
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'annotation: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(500, detail=f"Error adding annotation: {str(e)}")



