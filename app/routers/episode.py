from fastapi import APIRouter, HTTPException, Depends, UploadFile, Body, Form, File, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from pymongo.errors import DuplicateKeyError
from auth import (
    check_authorization,
    ensure_center_pepper_binding,
    ensure_resource_access,
    get_episode_access_query,
    parse_projects,
    resolve_user_center,
)
import httpx
from db import engine, Episode, ScrapedEpisode, Annotation, Job, JobStatus, Manufacturer, UserType, ProcessingTimeForEpisode, User, AIJob, EpisodeInfo
from typing import List, Annotated, Dict, Optional, Union
from odmantic import ObjectId
from services.diagnosis_service import DiagnosisService
from services.keycloak_service import get_keycloak_admin, get_clients_with_realm_role
import logging
from bson.binary import Binary
from datetime import datetime
from settings import AI_WORKER_URL
import os
from starlette.background import BackgroundTask
import time

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


async def resolve_episode_scope(episode: Episode | ScrapedEpisode) -> tuple[Optional[str], list[str]]:
    center = getattr(episode, "center", None)
    projects = list(getattr(episode, "projects", []) or [])

    if center:
        return center, projects

    scraped_episode = await engine.find_one(ScrapedEpisode, ScrapedEpisode.episode_id == episode.episode_id)
    if scraped_episode:
        return scraped_episode.center, list(getattr(scraped_episode, "projects", []) or [])

    return None, projects

''' Routes for episode handling '''

@episode_router.get("/search")
async def search(
    rights: Annotated[User, Depends(check_authorization("read-region-db"))],
    episode_id: Optional[str] = Query(None),
    episode_type: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=10000),
    sort_by: str = Query("patient_id"),
    sort_order: str = Query("asc")
) -> JSONResponse:
    """
    Recherche des épisodes en fonction de plusieurs critères avec pagination et tri.
    """
    try:
        query: Dict[str, object] = {}

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
        
        # Définir l'ordre de tri
        order = 1 if sort_order == "asc" else -1

        # Validation du champ de tri
        valid_sort_fields = ["episode_id", "patient_id", "episode_type", "manufacturer", "age_at_episode", "episode_duration"]
        if sort_by not in valid_sort_fields:
            raise HTTPException(status_code=400, detail=f"Invalid sort_by field. Must be one of: {', '.join(valid_sort_fields)}")

        scope_query = get_episode_access_query(rights)
        if scope_query:
            query = {"$and": [query, scope_query]} if query else scope_query

        # Exécuter la requête avec tri
        cursor = (
            engine.get_collection(Episode)
            .find(query)
            .sort(sort_by, order)
            .skip(skip)
            .limit(limit)
        )
        results = await cursor.to_list(length=limit)

        # Convertir les résultats pour JSON
        def convert_document(doc):
            doc["_id"] = str(doc["_id"])  # Convertir ObjectId en chaîne
            if "egm" in doc:  # Supprimer ou transformer les données binaires
                doc["egm"] = "Binary data omitted"
            for annotation in doc.get("annotations", []):
                if "_id" in annotation:
                    annotation["_id"] = str(annotation["_id"])
            return doc

        json_results = [convert_document(result) for result in results]
        total = await engine.get_collection(Episode).count_documents(query)

        # Retourner les résultats
        return JSONResponse(
            status_code=200,
            content={
                "results": json_results,
                "total": total,
                "page": page,
                "limit": limit,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche : {str(e)}")
        raise HTTPException(status_code=500, detail="Error searching episodes")
    
async def send_to_ai(manufacturer: str, episode_type: str, episode_id: str, jobs: List[str]):
    
    logger.info('Calling Keycloak Service...')
    
    realm_role = f"{manufacturer.lower()}.{episode_type}"
    logger.info(f"Vérification des rôles pour le fabricant {manufacturer} et le type d'épisode {episode_type}")
    
    ai_clients = get_clients_with_realm_role(role_name=realm_role)
    logger.info(f"Clients trouvés pour le rôle {realm_role}: {ai_clients}")

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
                        "id_model": ai_client["clientId"],
                        "job_id": job_id
                    }
                )
                logger.info(f"Requête envoyée à l'IA {ai_client['clientId']}: {response.status_code}")
                if response.status_code == 202:
                    logger.info(f"Requête acceptée par l'IA {ai_client['clientId']}, stockage du job ID dans mongodb sous la collection jobs")
                    await engine.save(Job(
                        job_id=job_id,
                        episode_id=episode_id,
                        id_model=ai_client["clientId"],
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
    request: Request,
    rights= Annotated[User, Depends(check_authorization("create-episode"))],
    patient_id: str = Form(...),
    manufacturer: str = Form(...),
    episode_type: str = Form(...),
    age_at_episode: int = Form(...),
    implant_model: str = Form(...),  # Champ à remplir si nécessaire
    episode_duration: str = Form(...),  # Correction du type de episode_duration
    episode_id: str = Form(...),
    center: Optional[str] = Form(None),
    projects: Optional[str] = Form(None),
) -> JSONResponse:
    try:
        jobs = []
        resolved_center = resolve_user_center(rights, center)
        await ensure_center_pepper_binding(request, resolved_center)
        resolved_projects = parse_projects(projects)

        # Vérifier si l'épisode existe déjà
        existing_episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        
        if existing_episode:
            existing_center, existing_projects = await resolve_episode_scope(existing_episode)
            if existing_episode.center is None:
                existing_episode.center = resolved_center
                if resolved_projects and not existing_episode.projects:
                    existing_episode.projects = resolved_projects
                await engine.save(existing_episode)
                existing_center = existing_episode.center
                existing_projects = existing_episode.projects

            ensure_resource_access(
                rights,
                center=existing_center,
                projects=existing_projects,
            )
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
                    "center": existing_episode.center,
                    "projects": existing_episode.projects,
                    "implant_model": existing_episode.implant_model,
                    "labels": labels,
                    "exists": True,
                    "annotated": True if existing_episode.annotations else False,
                    "egm_uploaded": True if existing_episode.egm else False,
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
            center=resolved_center,
            projects=resolved_projects,
            implant_model=implant_model,  # Champ à remplir si nécessaire
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
                "implant_model": episode.implant_model,
                "age_at_episode": episode.age_at_episode,
                "center": episode.center,
                "projects": episode.projects,
                "manufacturer": episode.manufacturer,
                "episode_type": episode.episode_type,
                "labels": labels,
                "exists": False,
                "annotated": False,
                "egm_uploaded": False
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'upload: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(status_code=422, detail=str(e))

@episode_router.post("/scraping")
async def scrape_episode(
    request: Request,
    rights: Annotated[User, Depends(check_authorization("create-episode"))],
    patient_id: str = Form(...),
    manufacturer: str = Form(...),
    episode_type: str = Form(...),
    age_at_episode: Union[int,str] = Form(...),
    implant_model: str = Form(...),  # Champ à remplir si nécessaire
    episode_duration: str = Form(...),  # Correction du type de episode_duration
    episode_id: str = Form(...),
    center: Optional[str] = Form(None),
    projects: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None)
) -> JSONResponse:
    
    ''' Lancement du scraping pour un épisode donné
    '''
    
    # check for an existing entry in the scraping database
    t_0 = time.perf_counter()
    resolved_center = resolve_user_center(rights, center)
    await ensure_center_pepper_binding(request, resolved_center)
    resolved_projects = parse_projects(projects)

    binary_files = None
    if files:
        binary_files = [Binary(await f.read()) for f in files]
    t_read = time.perf_counter()

    entry = ScrapedEpisode(
        episode_id=episode_id,
        patient_id=patient_id,
        manufacturer=manufacturer.lower(),
        episode_type=episode_type,
        age_at_episode=age_at_episode,
        implant_model=implant_model,
        episode_duration=episode_duration,
        center=resolved_center,
        projects=resolved_projects,
        egm=binary_files,
    )
    entry_doc = entry.model_dump(by_alias=True, exclude_none=True)

    coll = engine.get_collection(ScrapedEpisode)
    try:
        res = await coll.update_one(
            {"episode_id": episode_id},
            {"$setOnInsert": entry_doc},
            upsert=True,
        )
        created = res.upserted_id is not None
        status = 201 if created else 200
    except DuplicateKeyError:
        created = False
        status = 200

    t_upsert = time.perf_counter()
    logger.info(f"time_read_files={t_read - t_0:.4f}s time_db_upsert={t_upsert - t_read:.4f}s")

    return JSONResponse(
        status_code=status,
        content={
            "episode_id": episode_id,
            "patient_id": patient_id,
            "episode_type": episode_type,
            "age_at_episode": age_at_episode,
            "implant_model": implant_model,
            "episode_duration": episode_duration,
            "center": resolved_center,
            "projects": resolved_projects,
            "images_uploaded": True if status==201 else False,
            "created": created,
        },
    )
  
@episode_router.get("/{episode_id}/diagnostics")
async def get_episode_diagnostics(
    rights: Annotated[User, Depends(check_authorization("read-data"))],
    episode_id: str
    ) -> JSONResponse:
    """
    Récupère les diagnostics disponibles pour un épisode spécifique. Utilisé dans la web app
    """
    try:
        # Rechercher l'épisode par son ID
        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            raise HTTPException(404, detail='No episode with this ID.')
        center, projects = await resolve_episode_scope(episode)
        ensure_resource_access(rights, center=center, projects=projects)

        # Obtenir les diagnostics basés sur le fabricant et le type d'épisode
        diagnosis_service = DiagnosisService(engine)
        labels = await diagnosis_service.get_possible_labels(
            manufacturer=episode.manufacturer,
            episode_type=episode.episode_type
        )

        return JSONResponse(
            status_code=200,
            content={
                "episode_id": episode_id,
                "patient_id": episode.patient_id,
                "episode_type": episode.episode_type,
                "episode_duration": episode.episode_duration,
                "age_at_episode": episode.age_at_episode,
                "manufacturer": episode.manufacturer,
                "diagnostics": labels
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des diagnostics : {str(e)}")
        raise HTTPException(500, detail="Error retrieving diagnostics")

@episode_router.get("/{id}")
async def get_episode_by_id(
    rights: Annotated[User, Depends(check_authorization("read-data"))],
    id: ObjectId
    ) -> EpisodeInfo:
    logger.info(f"Requête reçue pour obtenir l'épisode avec id: {id} et auth_info: {rights}")
    """ 
    Get info about a given episode from its `id`
    """
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    center, projects = await resolve_episode_scope(episode)
    ensure_resource_access(rights, center=center, projects=projects)
    return EpisodeInfo(**episode.model_dump())


@episode_router.delete("/{id}")
async def delete_episode_by_id(
    auth_info : Annotated[User, Depends(check_authorization("delete-episode"))],
    id: ObjectId
    ) -> EpisodeInfo:
    logger.info(f"Requête reçue pour supprimer l'épisode avec id: {id} et auth_info: {auth_info}")
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    center, projects = await resolve_episode_scope(episode)
    ensure_resource_access(auth_info, center=center, projects=projects)
    await engine.delete(episode)
    return EpisodeInfo(**episode.model_dump())

@episode_router.put("/diagnoses")
async def update_diagnosis(
    auth_info: Annotated[User, Depends(check_authorization("update-labels"))], 
    diagnosis: str = Form(...),
    manufacturer: str = Form(...),
    labels: str = Form(...)
) -> JSONResponse:
    """
    Met à jour les diagnostics pour un fabricant spécifique - accessible aux experts uniquement
    """
    logger.info(f"🔄 Requête reçue pour mise à jour | Fab: {manufacturer} | Diag: {diagnosis} | Labels: {labels}")
    logger.info(f"labels: {labels}")

    # Vérifier si l'utilisateur est bien un expert

    if not auth_info:
        logger.error("❌ Aucune information utilisateur trouvée.")
        raise HTTPException(403, "User information is missing")

    logger.info(f"👤 Informations utilisateur: {auth_info}")

    username = auth_info.username
    realm_roles = auth_info.realm_roles
    
    logger.info(f"👤 Utilisateur: {username} | Rôles: {realm_roles}")
    
    try:
        manufacturer_enum = Manufacturer(manufacturer.lower())  # Convertir en minuscule et en Enum
    except ValueError:
        logging.error(f"❌ Fabricant '{manufacturer}' invalide.")
        raise ValueError(f"Invalid manufacturer: {manufacturer}")

    if "update_labels" not in realm_roles:
        logger.warning(f"⛔ Accès refusé pour {username} (pas le rôle 'update_labels')")
        raise HTTPException(403, "User not authorized to update labels")
    
    # Mettre à jour le diagnostic
    diagnosis_service = DiagnosisService(engine)
    
    try:
        update_result = await diagnosis_service.update_diagnosis(manufacturer_enum, diagnosis, labels)
        logger.info(f"🔍 Résultat de la mise à jour: {update_result}")
        
        logger.info('Vérification de la bonne mise à jour des diagnostics')
        updated_labels = await diagnosis_service.get_possible_labels(manufacturer_enum, diagnosis)
        logger.info(f"Labels mis à jour pour {manufacturer} - {diagnosis}: {updated_labels}")

        return JSONResponse(
            status_code=200,
            content={
                "message": "Diagnosis updated successfully",
                "manufacturer": manufacturer,
                "diagnosis": diagnosis,
                "labels": labels
            }
        )
    
    except Exception as e:
        logger.error(f"💥 Erreur lors de la mise à jour des diagnostics: {str(e)}")
        raise HTTPException(500, detail="Error updating diagnoses")
    
    
@episode_router.get("/diagnoses_labels/{manufacturer}")
async def get_diagnoses(
    manufacturer: str,
    auth_info: Annotated[User, Depends(check_authorization("read-region-db"))]  # Assurez-vous que l'utilisateur a le droit de lire les données
) -> JSONResponse:
    """
    Récupère les diagnostics disponibles pour un fabricant et tous les épisodes possibles - permet d'améliorer la réactivité du plugin vs. une requête par épisode pour certains cas d'usage
    """
    diagnosis_service = DiagnosisService(engine)
    
    manufacturer_enum = Manufacturer(manufacturer.lower())
    logger.info(f"manufactuer: {manufacturer_enum}")
    
    try:
        logger.info(auth_info)
        logger.info(f"Requête reçue pour récupérer les diagnostics | Fab: {manufacturer}")
        labels = await diagnosis_service.get_all_labels(manufacturer_enum)
        return JSONResponse(
            status_code=200,
            content={
                "manufacturer": manufacturer,
                "labels": labels
            }
    )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des diagnostics: {str(e)}")
        raise HTTPException(500, detail="Error retrieving diagnoses")


@episode_router.post("/processing_time")
async def post_processing_time(
    auth: Annotated[User, Depends(check_authorization("annotate-episode"))],
    annotation: str = Form(...),
    processing_time: str = Form(...),
    episode_id: str = Form(...),

) -> JSONResponse:
    """
    Stocke le temps de traitement pour un épisode spécifique
    """
    logger.info(f"total auth: {auth}")
    
    username = auth.username
    
    user_type = auth.user_type or "nurse"
    
    try:
        processing_time = float(processing_time)
    except ValueError:
        logger.error(f"Temps de traitement invalide: {processing_time}")
        raise HTTPException(400, "Invalid processing time")
    
    logger.debug(f"Requête reçue pour stocker le temps de traitement pour l'épisode {episode_id}")
    logger.debug(f"Temps de traitement reçu: {processing_time}")
    
    
    
    processing_time = ProcessingTimeForEpisode(
        episode_id=episode_id,
        processing_time=processing_time,
        annotation=annotation,
        user = username,
        user_type=UserType(user_type),
    )
    
    logger.info(f"processing_time: {processing_time}")
    
    await engine.save(processing_time)
    
    try:
        return JSONResponse(
            status_code=201,
            content={
                "message": "Processing time stored successfully",
                "episode_id": processing_time.episode_id,
                "processing_time": processing_time.processing_time
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du temps de traitement: {str(e)}")
        raise HTTPException(500, detail="Error storing processing time")
    
""" 
Routes for EGM handling
"""

@egm_router.get("/{episode_id}/egm")
async def get_episode_egm(
    episode_id: str, 
    auth: Annotated[User, Depends(check_authorization("read-region-db"))],
    collection: Optional[str] = "episodes"
    ):
    
    logger.info(f"Requête reçue pour obtenir l'EGM avec episode_id: {episode_id} et auth_info: {auth}")
    """
    Récupère l'EGM d'un épisode spécifique
    
    Parameters:
    - episode_id: Identifiant unique de l'épisode
    - user: Utilisateur authentifié (injecté automatiquement)
    
    Returns:
    - FileResponse contenant l'EGM
    """
    
    if collection not in ["episodes", "scraping"]:
        raise HTTPException(400, detail="Invalid collection. Must be 'episodes' or 'scraping'.")
    else:
        model = Episode if collection == "episodes" else ScrapedEpisode
    
    try:
        # Rechercher l'épisode par son ID
        episode = await engine.find_one(model, model.episode_id == episode_id)
        if not episode:
            raise HTTPException(404, detail='No episode with this ID.')
        center, projects = await resolve_episode_scope(episode)
        ensure_resource_access(auth, center=center, projects=projects)
        
        # Vérifier si l'EGM existe
        if not hasattr(episode, 'egm') or not episode.egm:
            raise HTTPException(404, detail='No EGM stored for this episode.')
        
        import base64
        
        # Handle both single binary and list of binaries
        if isinstance(episode.egm, list):
            # Multiple images - return JSON with all images as base64
            images = []
            for i, data in enumerate(episode.egm):
                if isinstance(data, Binary):
                    file_bytes = bytes(data)
                elif isinstance(data, (bytes, bytearray)):
                    file_bytes = data
                else:
                    try:
                        file_bytes = base64.b64decode(data)
                    except Exception:
                        file_bytes = data.encode() if isinstance(data, str) else data
                
                # Encode to base64 for JSON response
                base64_data = base64.b64encode(file_bytes).decode('utf-8')
                images.append({
                    "index": i,
                    "data": base64_data,
                    "format": "png"  # Assuming PNG for multiple images from Medtronic
                })
            
            return JSONResponse(
                status_code=200,
                content={
                    "episode_id": episode_id,
                    "type": "multiple",
                    "count": len(images),
                    "images": images
                }
            )
        else:
            # Single image - return as file
            data = episode.egm
            raw_data = data if isinstance(data, (bytes, bytearray, Binary)) else data.encode()
            
            # Try to detect if it's SVG (XML) or binary image
            if isinstance(raw_data, Binary):
                check_data = bytes(raw_data)
            else:
                check_data = raw_data
                
            if check_data.lstrip().startswith(b'<'):
                temp_file = f"/tmp/{episode_id}.svg"
                filename = f"episode_{episode_id}.svg"
                media_type = "image/svg+xml"
                file_bytes = check_data
            else:
                temp_file = f"/tmp/{episode_id}.png"
                filename = f"episode_{episode_id}.png" 
                media_type = "image/png"
                
                if isinstance(data, Binary):
                    file_bytes = bytes(data)
                elif isinstance(data, (bytes, bytearray)):
                    file_bytes = data
                else:
                    try:
                        file_bytes = base64.b64decode(data)
                    except Exception:
                        file_bytes = data.encode() if isinstance(data, str) else data

            # Write to temporary file
            with open(temp_file, "wb") as f:
                f.write(file_bytes)
            
            return FileResponse(
                path=temp_file,
                filename=filename,
                media_type=media_type,
                background=BackgroundTask(lambda: os.remove(temp_file))
            )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'EGM: {str(e)}")
        raise HTTPException(500, detail=str(e))


@egm_router.get("/{episode_id}/egm/download")
async def download_episode_egm_files(
    auth: Annotated[User, Depends(check_authorization("read-region-db"))],
    episode_id: str,
    collection: Optional[str] = "episodes"
    ) -> FileResponse:
    """
    Télécharge tous les fichiers EGM d'un épisode
    - Si plusieurs images: retourne un fichier ZIP
    - Si une seule image: retourne le fichier directement
    
    Parameters:
    - episode_id: Identifiant unique de l'épisode
    - auth: Utilisateur authentifié
    
    Returns:
    - FileResponse contenant soit un ZIP (plusieurs images) soit le fichier unique
    """
    logger.info(f"Requête reçue pour télécharger les fichiers EGM pour episode_id: {episode_id}")
    
    if collection not in ["episodes", "scraping"]:
        raise HTTPException(400, detail="Invalid collection. Must be 'episodes' or 'scraping'.")
    else:
        model = Episode if collection == "episodes" else ScrapedEpisode
    
    try:
        # Rechercher l'épisode par son ID
        episode = await engine.find_one(model, model.episode_id == episode_id)
        if not episode:
            raise HTTPException(404, detail='No episode with this ID.')
        center, projects = await resolve_episode_scope(episode)
        ensure_resource_access(auth, center=center, projects=projects)
        
        # Vérifier si l'EGM existe
        if not hasattr(episode, 'egm') or not episode.egm:
            raise HTTPException(404, detail='No EGM stored for this episode.')
        
        import base64
        import zipfile
        
        # Handle both single binary and list of binaries
        if isinstance(episode.egm, list) and len(episode.egm) > 1:
            # Multiple images - create ZIP file
            logger.info(f"Creating ZIP file for {len(episode.egm)} images")
            
            temp_zip = f"/tmp/{episode_id}_egm_images.zip"
            
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for i, data in enumerate(episode.egm):
                    # Extract binary data
                    if isinstance(data, Binary):
                        file_bytes = bytes(data)
                    elif isinstance(data, (bytes, bytearray)):
                        file_bytes = data
                    else:
                        try:
                            file_bytes = base64.b64decode(data)
                        except Exception:
                            file_bytes = data.encode() if isinstance(data, str) else data
                    
                    # Add to ZIP with appropriate filename
                    filename = f"egm_image_{i}.png"
                    zipf.writestr(filename, file_bytes)
                    logger.info(f"Added {filename} to ZIP ({len(file_bytes)} bytes)")
            
            return FileResponse(
                path=temp_zip,
                filename=f"episode_{episode_id}_egm_images.zip",
                media_type="application/zip",
                background=BackgroundTask(lambda: os.remove(temp_zip))
            )
        else:
            # Single image - return file directly
            logger.info("Returning single EGM file")
            
            if isinstance(episode.egm, list):
                data = episode.egm[0]
            else:
                data = episode.egm

            # Try to detect format
            raw_data = data if isinstance(data, (bytes, bytearray, Binary)) else data.encode()
            if isinstance(raw_data, Binary):
                check_data = bytes(raw_data)
            else:
                check_data = raw_data
                
            if check_data.lstrip().startswith(b'<'):
                filename = f"episode_{episode_id}.svg"
                media_type = "image/svg+xml"
                extension = "svg"
            else:
                filename = f"episode_{episode_id}.png"
                media_type = "image/png"
                extension = "png"

            # Extract binary data
            if isinstance(data, Binary):
                file_bytes = bytes(data)
            elif isinstance(data, (bytes, bytearray)):
                file_bytes = data
            else:
                try:
                    file_bytes = base64.b64decode(data)
                except Exception:
                    file_bytes = data.encode() if isinstance(data, str) else data

            # Create temporary file
            temp_file = f"/tmp/{episode_id}.{extension}"
            
            with open(temp_file, "wb") as f:
                f.write(file_bytes)
            
            return FileResponse(
                path=temp_file,
                filename=filename,
                media_type=media_type,
                background=BackgroundTask(lambda: os.remove(temp_file))
            )
        
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement des fichiers EGM: {str(e)}")
        raise HTTPException(500, detail=str(e))


@egm_router.post("/{episode_id}/egm", status_code=201)
async def post_episode_egm(
    user: Annotated[User, Depends(check_authorization("create-episode"))],
    episode_id: str,
    files: List[UploadFile] = File(default=[])
):
    
    try:
        logger.info(f"Tentative d'upload EGM pour l'épisode {episode_id} par l'utilisateur {user.username}")
        logger.info(f"Tentative d'upload EGM pour l'épisode {episode_id}")
        logger.info(f"Nombre de fichiers reçus: {len(files)}")
        logger.info(f"Type de files: {type(files)}")
        
        if not files:
            logger.error("Aucun fichier reçu")
            raise HTTPException(400, detail="No files provided")
        
        for file in files:
            logger.info(f"Fichier reçu: {file.filename}")
            logger.info(f"Content type: {file.content_type}")
            logger.info(f"Headers: {file.headers}")
            logger.info(f"File size: {file.size if hasattr(file, 'size') else 'Unknown'}")

        episode = await engine.find_one(Episode, Episode.episode_id == episode_id)
        if not episode:
            logger.error(f"Episode {episode_id} non trouvé")
            raise HTTPException(404, detail='No episode with this ID.')
        center, projects = await resolve_episode_scope(episode)
        ensure_resource_access(user, center=center, projects=projects)
        
        if len(files) == 1:
            # Si un seul fichier, on le traite comme un EGM unique
            content = await files[0].read()
            if not content:
                logger.error(f"Le fichier {files[0].filename} is empty")
                raise HTTPException(400, detail=f"File {files[0].filename} is empty")
            episode.egm = Binary(content)
        else:
            # Plusieurs fichiers, on stocke comme une liste de Binary
            binaries = []
            for upload in files:
                content = await upload.read()
                if not content:
                    logger.error(f"Le fichier {upload.filename} is empty")
                    raise HTTPException(400, detail=f"File {upload.filename} is empty")
                binaries.append(Binary(content))
            episode.egm = binaries
            

        episode.updated_at = datetime.now()  # Mettre à jour la date de modificationx
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
    except Exception as e:
        logger.error(f"Erreur lors de l'upload de l'EGM: {str(e)}")
        logger.exception("Traceback complet:")
        raise HTTPException(500, detail=f"Error storing EGM: {str(e)}")

''' Routes for annotation updates '''

@annotation_router.put("/{episode_id}/annotation")
async def put_episode_annotation(
    episode_id: str,
    auth_info: User = Depends(check_authorization("annotate-episode")),
    label: str = Body(..., embed=True),
    details: Optional[Dict] = Body(None)
) -> JSONResponse:
    logger.info(f"Tentative d'ajout d'annotation pour l'épisode {episode_id} par {auth_info.username}")
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
        center, projects = await resolve_episode_scope(episode)
        ensure_resource_access(auth_info, center=center, projects=projects)

        group = auth_info.user_type or "nurse"
        new_annotation = Annotation(
            user=auth_info.username,
            user_type=UserType(group),  
            label=label,
            details=details 
        )

        # Ajouter l'annotation à la liste des annotations de l'épisode
        episode.annotations.append(new_annotation)
        episode.updated_at = datetime.now()  # Mettre à jour la date de modification
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
