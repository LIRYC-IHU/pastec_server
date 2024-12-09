from asyncio import Queue, create_task
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional
import logging
from datetime import datetime
from models import AIJob, ModelRegistry, TaskData
import httpx
from bson import ObjectId
import os
from auth import get_jwt_token

logger = logging.getLogger(__name__)

class AITaskQueue:
    def __init__(self):
        self.queue = Queue()
        self.model_registry = ModelRegistry()
        self.is_processing = False
        
    async def add_task(self, model_name: str, job_id: str) -> None:
        """Ajoute une tâche à la queue"""
        await self.queue.put(TaskData(model_name=model_name, job_id=job_id))
        logger.info(f"Tâche ajoutée à la queue: {model_name, job_id}")
        
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
        model_name = task.model_name
        job_id = task.job_id
        
        logger.info(f"Traitement de la tâche: {job_id, model_name}")
        
        try:
            
            # Récupération de l'EGM
            egm_data = await self._fetch_egm(job_id, model_name)
            
            # Analyse avec le modèle
            prediction = await self.model_registry.run_inference(model_name, egm_data)
            
            # Envoi du résultat
            await self._submit_annotation(job_id, prediction, model_name)
            
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement: {str(e)}")
    

    async def _fetch_egm(self, job_id: str, model_name: str) -> bytes:
        """Récupère l'EGM depuis l'API"""
        async with httpx.AsyncClient() as client:
            token = await get_jwt_token(model_name)
            headers = {'Authorization': f'Bearer {token}'}
            response = await client.get(
                f"{os.getenv('FASTAPI_URL')}/ai/{job_id}/egm",
                headers=headers
            )
            if response.status_code == 200:
                logger.info("requête réussie")
            if response.status_code == 404:
                logger.warning(f"EGM non trouvé pour job_id: {job_id}, model_name: {model_name}")
                return b""
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError(f"Erreur lors de la récupération de l'EGM: {response.status_code}")
            return response.content

    async def _submit_annotation(
        self,
        job_id: str,
        prediction: Dict,
        model_name: str
    ) -> AIJob:
        """Soumet l'annotation à l'API"""
        ai_job = AIJob(
            job_id=job_id,
            model_name=model_name,
            annotation=prediction["prediction"],
            confidence=prediction.get("confidence", 0.0),
            details=prediction.get("details", {})  # Ajout du champ 'details'
        )
        
        async with httpx.AsyncClient() as client:
            token = await get_jwt_token(model_name)
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