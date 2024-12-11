import os
from typing import Dict, Any

class Config:
    """Configuration globale du worker"""
    
    KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
    FASTAPI_URL = os.getenv("FASTAPI_URL", "http://api:8000")
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
    
    # Configuration des modèles
    MODEL_CONFIG = {
        "dummy_model": {
            "manufacturer": "medtronic",
            "episode_types": ["vt", "vf"],
            "batch_size": 32,
            "timeout": 30  # secondes
        }
    }
    
    @classmethod
    def get_model_config(cls, id_model: str) -> Dict[str, Any]:
        """Récupère la configuration d'un modèle"""
        return cls.MODEL_CONFIG.get(id_model, {}) 