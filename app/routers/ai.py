from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse, FileResponse
from auth import get_auth_info, get_user_info
from schemas import AIJob, User
from db import engine, Episode, Annotation, Job, JobStatus, UserType
from typing import List, Dict, Optional, Annotated
from schemas import AIJob, User, Episode
from odmantic import ObjectId
from datetime import datetime
import httpx
import logging
from bson.binary import Binary
from settings import AI_WORKER_URL
from starlette.background import BackgroundTask

logger = logging.getLogger(__name__)

# Router pour l'IA
ai_router = APIRouter(
    prefix="/ai",
    tags=["AI Processing"]
)

@ai_router.post("/{episode_id}/ai", status_code=202)
async def send_job_to_ai(
    episode_id: str, 
    user: Annotated[User, Depends(get_user_info)], 
    ai_clients: List[str]
):
    logger.info(f"Envoi de l'EGM aux modèles IA pour l'épisode {episode_id} par l'utilisateur {user.username}")
    """Send EGM to AI for analysis"""
    logger.info(f"Envoi de l'EGM aux modèles IA pour l'épisode {episode_id}")
    
    # Création d'un job pour chaque modèle
    jobs = []
    for ai_user in ai_clients:
        # Créer un job dans MongoDB
        job = Job(
            job_id=str(ObjectId()),
            episode_id=episode_id,
            model_name=ai_user,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            annotation=None,
            confidence=None,
            details=None
        )
        
        job_result = await engine.save(Job, job_result)
        job_id = str(job_result.inserted_id)
        
        logger.info(f"Job créé avec succès pour l'IA {ai_user} avec job_id: {job_id}")
        
        # Envoyer la requête au worker
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{AI_WORKER_URL}/process/{job_id}",
                    json={
                        "model_name": ai_user,
                        "job_id": job_id
                    }
                ) 
                if response.status_code != 202:
                    raise Exception(f"Erreur lors de l'envoi à l'IA {ai_user}: {response.text}")
                jobs.append({
                    "job_id": job_id,
                    "model_name": ai_user,
                    "status": "processing"
                })
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi à l'IA {ai_user}: {str(e)}")
            # Mettre à jour le statut du job
            await engine.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": {"status": "failed", "error": str(e)}}
            )
    
    return {
        "message": "Analysis requests sent",
        "jobs": jobs
    }

@ai_router.get("/{job_id}/egm")
async def get_egm_from_job(
    job_id: str,
    auth_info: dict = Depends(get_auth_info)
) -> FileResponse:
    logger.info(f"Requête reçue pour obtenir l'EGM avec job_id: {job_id} et auth_info: {auth_info}")
    """
    Récupère l'EGM d'un épisode spécifique
    
    Parameters:
    - job_id: Identifiant unique du job
    - user: Utilisateur authentifié (injecté automatiquement)
    
    Returns:
    - FileResponse contenant l'EGM
    """
    
    logger.info(f"Requête reçue par {auth_info['type']}: {auth_info['info']}")
    
    try:
        # Rechercher le job par son ID dans la collection "jobs"
        job = await engine.find_one(Job, Job.job_id == job_id)
        if not job:
            logger.error(f"Aucun job trouvé avec l'ID: {job_id}")
            raise HTTPException(404, detail='No job with this ID.')
        if job.status != JobStatus.PENDING:
            logger.error(f"Le job avec l'ID {job_id} n'est pas en statut pending.")
            raise HTTPException(403, detail='No accepted job for this ID.')
        
        logger.info(f"found one job with id {job_id}")
        
        # Rechercher l'épisode par son ID
        episode = await engine.find_one(Episode, Episode.episode_id == job.episode_id)
        if not episode:
            logger.error(f"Aucun épisode trouvé avec l'ID: {job.episode_id}")
            raise HTTPException(404, detail='No episode with this ID.')
        
        # Vérifier si l'EGM existe
        if not hasattr(episode, 'egm') or not episode.egm:
            logger.warning(f"Aucun EGM stocké pour l'épisode avec l'ID: {job['episode_id']}")
            return JSONResponse(status_code=404, content={"message": "No EGM stored for this episode."})
        
        # Créer un fichier temporaire pour stocker l'EGM
        temp_file = f"/tmp/{episode.episode_id}.svg"
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
            filename=f"episode_{episode.episode_id}.svg",
            media_type="image/svg+xml",
            background=BackgroundTask(lambda: os.remove(temp_file))
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'EGM: {str(e)}")
        raise HTTPException(500, detail=str(e))

@ai_router.put("/{job_id}/annotation", status_code=200)
async def add_ai_annotation(
    job_id: str,
    auth_info: dict = Depends(get_auth_info),
    ai_job: AIJob = Body(...)
) -> JSONResponse:
    logger.info(f"Tentative d'ajout d'annotation pour le job {job_id} par {auth_info['type']}: {auth_info['info']}")
    
    try:
        # Rechercher le job par son ID
        job = await engine.find_one(Job, Job.job_id == job_id)
        if not job:
            raise HTTPException(404, detail='No job with this ID.')
        if job.status != "pending":
            raise HTTPException(403, detail='Job is not in pending status.')
        
        # Rechercher l'épisode par son ID
        episode = await engine.find_one(Episode, Episode.episode_id==job.episode_id)
        if not episode:
            raise HTTPException(404, detail='No episode with this ID.')
        
        # Créer la nouvelle annotation
        new_annotation = Annotation(
            user=ai_job.model_name,
            user_type=UserType.AI,
            label=ai_job.annotation,
            details=ai_job.details
        )
        
        # Ajouter l'annotation à la liste des annotations de l'épisode
        episode.annotations.append(new_annotation)
        await engine.save(episode)
        
        # Mettre à jour le statut du job
        job.status = JobStatus.COMPLETED
        await engine.save(job)
        
        logger.info(f"Annotation ajoutée avec succès pour le job {job_id}")
        return JSONResponse(
            status_code=200,
            content={
                "message": "Annotation added successfully",
                "job_id": job_id,
                "annotation": {
                    "user": new_annotation.user,
                    "user_type": new_annotation.user_type,
                    "label": new_annotation.label,
                    "details": new_annotation.details
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'annotation pour le job {job_id}: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(500, detail=f"Error adding annotation: {str(e)}")
