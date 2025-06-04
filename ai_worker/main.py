from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
from queue_manager import AITaskQueue
from bson import ObjectId
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models import TaskData
import test_keys
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
task_queue = AITaskQueue()

class ProcessRequest(BaseModel):
    id_model: str  # Remplacez id_model par id_model

@app.post("/process/{job_id}", status_code=202)
async def process(job_id: str, request: ProcessRequest):
    """Ajoute une tâche à la queue"""
    await task_queue.add_task(request.id_model, job_id)  # Remplacez id_model par id_model
    return {"message": "Tâche ajoutée à la queue"}

@app.get("/queue/status")
async def get_queue_status():
    """Récupère le statut de la queue"""
    return {
        "queue_size": task_queue.queue.qsize(),
        "is_processing": task_queue.is_processing
    }
    
@app.get("/queue/job_status/{job_id}")
async def get_job_status(job_id: str):
    """Récupère le statut d'une tache dans la queue via son job_id"""
    return task_queue.get_job_status(job_id)

@app.post('/test')
async def test(
    client_id: str
) -> JSONResponse:
    """Test de la connexion avec le serveur FastAPI"""
    try:
        egm = await test_keys.e2e(client_id)
        
        return  JSONResponse(
            status_code=200,
            content={
                "message": "Test réussi",
                "egm": egm.decode('utf-8')  # Convertir les octets en chaîne de caractères
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du test: {str(e)}")