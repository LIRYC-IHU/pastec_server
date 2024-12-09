import logging

logger = logging.getLogger(__name__)

class DummyModel:
    def __init__(self):
        self.message = "This is a placeholder for future models"
        logger.info("DummyModel initialisé")

    async def inference(self, egm_data: bytes) -> dict:
        """Fonction d'inférence simple pour les tests"""
        logger.info("Exécution de l'inférence dummy")
        return {
            "prediction": self.message,
            "confidence": 1.0,
            "model_type": "dummy",
            "timestamp": "2024-03-21",
            "details": {}  # Ajout du champ 'details'
        }

def register_model(registry):
    """Enregistre le modèle dans le registre"""
    try:
        model = DummyModel()
        registry._models["dummy_model"] = {
            "inference_fn": model.inference,
            "manufacturer": "test",
            "episode_types": ["test"],
            "version": "1.0.0"
        }
        logger.info("DummyModel enregistré avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du DummyModel: {str(e)}")