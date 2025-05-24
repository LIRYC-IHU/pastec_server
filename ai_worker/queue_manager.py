from asyncio import Queue, create_task
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional
import logging
from datetime import datetime
from models import AIJob, ModelRegistry, TaskData
import httpx
from bson import ObjectId
import os
from auth import get_access_token
from operator import attrgetter

logger = logging.getLogger(__name__)

class AITaskQueue:
    def __init__(self):
        self.queue = Queue()
        self.model_registry = ModelRegistry()
        self.is_processing = False
        
    async def add_task(self, id_model: str, job_id: str) -> None:
        """Ajoute une tâche à la queue"""
        await self.queue.put(TaskData(id_model=id_model, job_id=job_id))
        logger.info(f"Tâche ajoutée à la queue: {id_model, job_id}")
        
        if not self.is_processing:
            create_task(self.process_queue())

    async def process_queue(self) -> None:
        """Traite les tâches de la queue une par une"""
        self.is_processing = True
        
        while not self.queue.empty():
            task = await self.queue.get()
            try:
                await self._process_task(task)
            except Exception as e:
                logger.error(f"Erreur lors du traitement de la tâche: {str(e)}")
            finally:
                self.queue.task_done()
                
        self.is_processing = False

    async def _process_task(self, task: TaskData) -> None:
        """Traite une tâche individuelle"""
        id_model = task.id_model
        job_id = task.job_id

        logger.info(f"Traitement de la tâche: {job_id, id_model}")

        try:
            # Récupération de l'EGM
            egm_data = await self._fetch_egm(job_id, id_model)
            episode_type_data = await self._fetch_episode_type(job_id, id_model)

            if not egm_data:
                raise ValueError(f"Aucune donnée EGM reçue pour job_id: {job_id}")

            # Exécution de l'inférence
            prediction = await self.model_registry.run_inference(id_model, egm_data, episode_type_data.get('episode_type'))

            # Soumission du résultat
            await self._submit_annotation(job_id, prediction, id_model)

        except Exception as e:
            logger.error(f"Erreur lors du traitement de la tâche {job_id}: {e}")
    

    async def _fetch_egm(self, job_id: str, id_model: str) -> bytes:
        """Récupère l'EGM depuis l'API"""
        async with httpx.AsyncClient() as client:
            key_model_path = f"/ai_worker/private_keys/key_{id_model}.pem"
            token = await get_access_token(id_model, key_model_path)
            headers = {'Authorization': f'Bearer {token}'}

            try:
                response = await client.get(
                    f"{os.getenv('FASTAPI_URL')}/ai/{job_id}/egm",
                    headers=headers
                )
                response.raise_for_status()

                if response.status_code == 200:
                    logger.info("Requête réussie pour l'EGM.")
                    return response.content

                if response.status_code == 404:
                    logger.warning(f"EGM non trouvé pour job_id: {job_id}, id_model: {id_model}")
                    return b""

            except httpx.RequestError as e:
                logger.error(f"Erreur réseau lors de la récupération de l'EGM: {e}")
                raise ValueError("Erreur réseau lors de la récupération de l'EGM")

            except httpx.HTTPStatusError as e:
                logger.error(f"Erreur HTTP lors de la récupération de l'EGM: {e}")
                raise ValueError(f"Erreur HTTP {e.response.status_code} lors de la récupération de l'EGM")
    
    async def _fetch_episode_type(self, job_id: str, id_model: str) -> dict:

        url = f"{os.getenv('FASTAPI_URL')}/ai/{job_id}/episode_type"
        
        async with httpx.AsyncClient() as client:
            key_model_path = f"/ai_worker/private_keys/key_{id_model}.pem"
            token = await get_access_token(id_model, key_model_path)
            headers = {'Authorization': f'Bearer {token}'}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                logger.info(f"Type d'épisode obtenu avec succès pour job_id: {job_id}")
                logger.info(f"Type d'épisode: {response.json()}")
                return response.json()
            else:
                logger.error(f"Erreur lors de l'obtention du type d'épisode: {response.status_code} {response.text}")
                response.raise_for_status()


    async def _submit_annotation(
        self,
        job_id: str,
        prediction: Dict,
        id_model: str
    ) -> AIJob:
        """Soumet l'annotation à l'API"""
        logger.info(f"prediction:{prediction}")
        ai_job = AIJob(
            job_id=job_id,
            id_model=id_model,
            annotation=str(prediction["prediction"]),
            confidence=prediction.get("confidence", 0.0),
            details=prediction.get("details", {})  # Ajout du champ 'details'
        )
        
        async with httpx.AsyncClient() as client:
            token = await get_access_token(id_model, f"/ai_worker/private_keys/key_{id_model}.pem")
            headers = {'Authorization': f'Bearer {token}'}
            response = await client.put(
                f"{os.getenv('FASTAPI_URL')}/ai/{job_id}/annotation",
                headers=headers,
                json=ai_job.model_dump()  # Convertir l'objet AIJob en dictionnaire
            )
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError(f"Erreur lors de la soumission de l'annotation: {response.status_code}")
            return response.content