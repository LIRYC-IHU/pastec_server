from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from db import DiagnosesCollection, Manufacturer
import logging

logger = logging.getLogger(__name__)

'''
Permet de récupérer les labels possibles pour un épisode donné
'''

class DiagnosisService:
    def __init__(self, engine: AsyncIOMotorClient):
        self.engine = engine
        
    async def get_possible_labels(self, manufacturer: Manufacturer, episode_type: str) -> List[str]:
        diagnoses = await self.engine.find_one(DiagnosesCollection)
        if not diagnoses:
            logger.warning("Aucun diagnostic trouvé dans la collection")
            return []
            
        # Convertir le manufacturer en string avec la première lettre en majuscule
        manufacturer_key = manufacturer.value.capitalize()
        logger.info(f"Clé manufacturer recherchée: {manufacturer_key}")
        
        # Récupérer les diagnostics pour ce manufacturer
        manufacturer_diagnoses = diagnoses.manufacturer_diagnoses.get(manufacturer_key, {})
        
        # Récupérer les labels pour ce type d'épisode
        labels = manufacturer_diagnoses.get(episode_type, [])
        logger.info(f"Labels trouvés pour {episode_type}: {labels}")
        
        # Si aucun label trouvé, essayer avec "Episodes without diagnoses"
        if not labels:
            labels = manufacturer_diagnoses.get("Episodes without diagnoses", [])
            logger.info(f"Labels par défaut utilisés: {labels}")
            
        return labels if labels != [""] else []