from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse, FileResponse
from auth import check_authorization
from db import engine, Episode, Annotation, Job, JobStatus, UserType, AIJob, User
from typing import List, Dict, Optional, Annotated
from odmantic import ObjectId
from datetime import datetime
import httpx
import logging
import os
from bson.binary import Binary
from settings import AI_WORKER_URL
from starlette.background import BackgroundTask
from services.keycloak_service import upload_key, get_client_rep, register_new_model


logger = logging.getLogger(__name__)

# Router pour l'IA
ai_router = APIRouter(
    prefix="/ai",
    tags=["AI Processing"]
)

@ai_router.post("/{episode_id}/ai", status_code=202)
async def send_job_to_ai(
    episode_id: str, 
    auth: Annotated[User, Depends(check_authorization("ai-model"))], 
    ai_clients: List[str]
):
    logger.info(f"Envoi de l'EGM aux modèles IA pour l'épisode {episode_id} par l'utilisateur {auth.username}")
    
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
    auth: dict = Depends(check_authorization("ai-model"))
) -> FileResponse:
    logger.info(f"Requête reçue pour obtenir l'EGM avec job_id: {job_id} et auth_info: {auth}")
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
    auth: dict = Depends(check_authorization("ai-model")),
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
        user_type=UserType.AI_MODEL,
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
    auth: User = Depends(check_authorization("read-data"))
) -> JSONResponse:
    logger.info(f"Requête reçue pour obtenir le statut du job {job_id} par l'utilisateur {auth.username}")
    
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
                    "id_model": job.id_model,
                    "status": job.status,
                    "updated_at": str(job.updated_at)
                }
            )
        else:
            logger.info(f"Le job {job_id} est terminé et a renvoyé le résultat {job.annotation}")
            return JSONResponse(
                status_code=200,
                content={
                    "job_id": job.job_id,
                    "job_annotation": job.annotation,
                    "id_model": job.id_model,
                    "status": job.status,
                    "created_at": str(job.created_at),
                    "updated_at": str(job.updated_at)
                }
            )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut du job {job_id}: {str(e)}")
        raise HTTPException(500, detail=f"Error getting job status: {str(e)}")
    
@ai_router.get("/{job_id}/episode_type")
async def get_episode_type(
    job_id: str,
    auth: User = Depends(check_authorization('ai-model'))
) -> JSONResponse:
    logger.info(f"Requête reçue pour obtenir le type d'épisode pour le job {job_id} par l'utilisateur {auth}")
    
    try:
        # Rechercher le job par son ID
        job = await engine.find_one(Job, Job.job_id == job_id)
        if not job:
            raise HTTPException(404, detail='No job with this ID.')
        
        episode = await engine.find_one(Episode, Episode.episode_id == job.episode_id)
        if not episode:
            raise HTTPException(404, detail='No episode with this ID.')
        
        return JSONResponse(
            status_code=200,
            content={
                "manufacturer": episode.manufacturer,
                "episode_type": episode.episode_type
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du type d'épisode pour le job {job_id}: {str(e)}")
        raise HTTPException(500, detail=f"Error getting episode type: {str(e)}")
    
@ai_router.post("/model_registration")
async def register_model(
    model_name: str = Body(..., embed=True),
    models: List[str] = Body(..., embed=True),
    manufacturer: str = Body(..., embed=True),
    auth: User = Depends(check_authorization('create-client'))
) -> JSONResponse:
    
    # construct roles list
    roles = [f"{manufacturer.lower()}.{roles}" for roles in models]
    
    try:
        logger.info(f"Requête reçue pour enregistrer le modèle {model_name} par l'utilisateur {auth.username}")
        
        response = await register_new_model(
            model_name=model_name,
            roles=roles
        )
        return JSONResponse(
            status_code=201,
            content={
                "message": f"Model {model_name} registered successfully",
                "model_name": model_name
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du modèle {model_name}: {str(e)}")
        raise HTTPException(500, detail=f"Error registering model: {str(e)}")
    
@ai_router.get("/{client_id}/client_representation")
async def get_client_representation( 
    client_id: str,
    auth: User = Depends(check_authorization('pastec-admin'))
) -> JSONResponse:
    try:
        client_representation = await get_client_rep(client_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "client_representation": client_representation
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la représentation du client: {str(e)}")
        raise HTTPException(500, detail=f"Error getting client representation: {str(e)}")

@ai_router.post('/key_pair')
async def create_key_pair(
    client_id: str,
    auth: User = Depends(check_authorization('pastec-admin'))
) -> FileResponse:
    try:
        logger.info(f"Requête reçue pour créer une paire de clés pour le client {client_id} par l'utilisateur {auth.username}")
    
        private_key = await upload_key(client_id)
        logger.info(f"Clé générée pour le client {client_id}: {private_key is not None}")
        logger.info(f"Type de la clé privée: {type(private_key)}")
        logger.info(private_key[:100])
        
        temp_file = f"/tmp/ai_{client_id}.pem"
        with open(temp_file, "wb") as f:
            f.write(private_key)
        
        return FileResponse(
            path=temp_file,
            filename=f"ai_{client_id}.pem",
            media_type="application/x-pem-file",
            background=BackgroundTask(lambda: os.remove(temp_file))
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la paire de clés pour le client {client_id}: {str(e)}")
        raise HTTPException(500, detail=f"Error creating key pair: {str(e)}")