from typing import Dict, Any
import os

class ModelConfig:
    MODELS = {
        "bsc_af_model": {
            "client_id": "ai-bsc-af-model",
            "private_key_path": "/certs/bsc_af_model/private.key",
            "certificate_path": "/certs/bsc_af_model/cert.pem",
            "keycloak_url": os.getenv("KEYCLOAK_URL", "http://keycloak:8080"),
            "realm": os.getenv("KEYCLOAK_REALM", "my-realm"),
            "manufacturer": "boston",
            "episode_types": ["AT/AF"]
        }
    }

    @classmethod
    def get_model_config(cls, id_model: str) -> Dict[str, Any]:
        return cls.MODELS.get(id_model, {}) 