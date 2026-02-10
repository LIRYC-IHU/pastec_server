from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime
from importlib import import_module
import os
import logging

logger = logging.getLogger(__name__)

class TaskData(BaseModel):
    id_model: str  # Remplacez id_model par id_model
    job_id: str

class AIJob(BaseModel):
    job_id: str
    id_model: str
    annotation: str
    confidence: Optional[float]
    details: Optional[Dict]
    
class ModelRegistry:
    """Registre des modèles d'IA disponibles"""
    def __init__(self):
        self._models = {}
        self._load_models()
        
    def _load_models(self):
        """Charge automatiquement les modèles depuis le dossier ai_models"""
        models_dir = os.path.join(os.path.dirname(__file__), 'ai_models')
        logger.debug(f"Chargement des modèles depuis {models_dir}")
        try:
            files = os.listdir(models_dir)
            logger.debug(f"Fichiers trouvés: {files}")
            
            for filename in files:
                if filename.endswith('.py') and not filename.startswith('__'):
                    module_name = filename[:-3]
                    logger.debug(f"Tentative de chargement du module: {module_name}")
                    try:
                        module = import_module(f'ai_models.{module_name}')
                        if hasattr(module, 'register_model'):
                            module.register_model(self)
                            logger.debug(f"Module {module_name} chargé avec succès")
                    except Exception as e:
                        logger.error(f"Erreur lors du chargement du modèle {module_name}: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"Erreur lors du listage des modèles: {str(e)}", exc_info=True)
    
    async def run_inference(self, id_model: str, egm_data: bytes, episode_type: str) -> Dict:
        """Exécute l'inférence sur un modèle spécifique"""
        if id_model not in self._models:
            raise ValueError(f"Modèle {id_model} non trouvé")
            
        model_info = self._models[id_model]
        return await model_info["inference_fn"](egm_data, episode_type)