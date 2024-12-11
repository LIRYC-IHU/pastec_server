from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse, FileResponse
from auth import get_auth_info, get_user_info
from schemas import AIJob, User
from db import engine, Episode, Annotation, Job, JobStatus, UserType
from typing import List, Dict, Optional, Annotated
from schemas import AIJob, User
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
    
    # Création d'un job pour chaque modèle
    jobs = []
    for ai_user in ai_clients:
        # Créer un job dans MongoDB
        job = Job(
            job_id=str(ObjectId()),
            episode_id=episode_id,
            id_model=ai_user,  # Remplacez id_model par id_model
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
                        "id_model": ai_user,  # Remplacez id_model par id_model
                        "job_id": job_id
                    }
                ) 
                if response.status_code != 202:
                    raise Exception(f"Erreur lors de l'envoi à l'IA {ai_user}: {response.text}")
                jobs.append({
                    "job_id": job_id,
                    "id_model": ai_user,
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
async def get_egm(
    job_id: str,
    auth_info: dict = Depends(get_auth_info)
) -> FileResponse:
    logger.info(f"Requête reçue pour obtenir l'EGM avec job_id: {job_id} et auth_info: {auth_info}")
    try:
        # Rechercher le job par son ID dans la collection "jobs"
        job = await engine.find_one(Job, Job.job_id == job_id)
        if not job:
            logger.error(f"Aucun job trouvé avec l'ID: {job_id}")
            raise HTTPException(404, detail='No job with this ID.')
        if job.status != JobStatus.PENDING:
            logger.error(f"Le job avec l'ID {job_id} n'est pas en statut pending.")
            raise HTTPException(403, detail='No accepted job for this ID.')

        episode_id = str(job.episode_id)
        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            logger.error(f"Aucun épisode trouvé pour episode_id: {episode_id}")
            raise HTTPException(404, detail='No episode with this ID.')

        if not hasattr(episode, 'egm') or not episode.egm:
            logger.warning(f"Aucun EGM stocké pour l'épisode avec l'ID: {episode_id}")
            return JSONResponse(status_code=404, content={"message": "No EGM stored for this episode."})

        temp_file = f"/tmp/{episode.episode_id}.svg"
        with open(temp_file, "wb") as f:
            if isinstance(episode.egm, Binary):
                f.write(episode.egm)
            else:
                import base64
                f.write(base64.b64decode(episode.egm))

        return FileResponse(
            path=temp_file,
            filename=f"episode_{episode.episode_id}.svg",
            media_type="image/svg+xml",
            background=BackgroundTask(lambda: os.remove(temp_file))
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'EGM pour le job {job_id}: {str(e)}")
        raise HTTPException(500, detail=f"Error getting EGM: {str(e.with_traceback(None))}")

@ai_router.put("/{job_id}/annotation", status_code=200)
async def add_ai_annotation_to_db(
    job_id: str,
    auth_info: dict = Depends(get_auth_info),
    ai_job: AIJob = Body(...)
) -> JSONResponse:
    # 1. Récupération du job
    job = await engine.find_one(Job, Job.job_id == job_id)
    if not job:
        raise HTTPException(404, detail='No job with this ID.')
    if job.status != "pending":
        raise HTTPException(403, detail='Job is not in pending status.')
    
    # 2. Création de la nouvelle annotation
    new_annotation = Annotation(
        user=ai_job.id_model,  # Assurez-vous que id_model est correct
        user_type=UserType.AI,
        label=ai_job.annotation,
        details=ai_job.details
    )
    
    # 3. Recherche de l'épisode lié au job
    episode = await engine.find_one(Episode, Episode.episode_id == job.episode_id)
    if not episode:
        raise HTTPException(404, detail='No episode with this ID.')
    
    # 4. Ajout de l'annotation à l'épisode
    episode.annotations.append(new_annotation)
    await engine.save(episode)
    
    # 5. Mise à jour du job: statut, annotation, etc.
    job.status = JobStatus.COMPLETED
    job.updated_at = datetime.utcnow()
    job.annotation = ai_job.annotation
    job.confidence = ai_job.confidence
    job.details = ai_job.details
    await engine.save(job)
    logger.info("Job status updated")
    
    return JSONResponse(
        status_code=200,
        content={
            "message": "Annotation added successfully",
            "episode_id": job.episode_id,
            "annotation": {
                "user": new_annotation.user,
                "user_type": new_annotation.user_type,
                "label": new_annotation.label,
                "details": new_annotation.details
            },
            "job_id": job_id,
            "status": job.status
        }
    ) 

@ai_router.get("/jobs")
async def get_job_status(
    job_id: str,
    user_info: User = Depends(get_user_info)
) -> JSONResponse:
    logger.info(f"Requête reçue pour obtenir le statut du job {job_id} par l'utilisateur {user_info.username}")
    
    try:
        # Rechercher le job par son ID
        job = await engine.find_one(Job, Job.job_id == job_id)
        if not job:
            raise HTTPException(404, detail='No job with this ID.')
        
        logger.info(f"Job trouvé avec succès pour l'ID {job_id}")
        
        if job.status != JobStatus.COMPLETED:
            logger.info(f"Le job {job_id} n'est pas terminé")
            return JSONResponse(
                status_code=202,
                content={
                    "status": job.status,
                    "updated_at": job.updated_at
                }
            )
        else:
            logger.info(f"Le job {job_id} est terminé et a renvoyé le résultat {job.annotation}")
            return JSONResponse(
                status_code=200,
                content={
                    "job_id": job.job_id,
                    "episode_id": job.episode_id,
                    "id_model": job.id_model,
                    "status": job.status,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at
                }
            )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut du job {job_id}: {str(e)}")
        raise HTTPException(500, detail=f"Error getting job status: {str(e)}")