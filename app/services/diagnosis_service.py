from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from db import DiagnosesCollection, Manufacturer
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

'''
Permet de récupérer les labels possibles pour un épisode donné
'''

class DiagnosisService:
    def __init__(self, engine: AsyncIOMotorClient):
        self.engine = engine
        
    async def get_possible_labels(self, manufacturer: Manufacturer, episode_type: str) -> List[str]:
        
        try: 
            manufacturer_key = manufacturer.value.capitalize()
            diagnoses = await self.engine.find_one(
                DiagnosesCollection, 
                {"manufacturer_diagnoses": {"$exists": True}, f"manufacturer_diagnoses.{manufacturer_key}": {"$exists": True}}
            )
            
            if not diagnoses:
                logger.warning("Aucun diagnostic trouvé dans la collection")
                return []
                
            # Convertir le manufacturer en string avec la première lettre en majuscule
            manufacturer_key = manufacturer.value.capitalize()
            logger.info(f"Clé manufacturer recherchée: {manufacturer_key}")
            
            # Récupérer les diagnostics pour ce manufacturer
            logger.info(f"Diagnostics trouvés pour {manufacturer_key}: {diagnoses}")
            
            # Récupérer les labels pour ce type d'épisode
            labels = diagnoses.manufacturer_diagnoses[manufacturer_key].get(episode_type, [])
            logger.info(f"Labels trouvés pour {episode_type}: {labels}")
            
            # Si aucun label trouvé, essayer avec "Episodes without diagnoses"
            if not labels:
                logger.warning("Aucun label trouvé pour cet épisode, tentative avec 'Episodes without diagnoses'")
                labels = diagnoses[manufacturer_key]["Episodes without diagnoses"]
                logger.info(f"Labels trouvés pour 'Episodes without diagnoses': {labels}")
                logger.info(f"Labels par défaut utilisés: {labels}")
                
            return labels if labels != [""] else []
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des labels possibles: {str(e)}")
            return []
    
    async def get_all_labels(self, manufacturer: Manufacturer) -> dict[str]:
        try:
            manufacturer_key = manufacturer.value.capitalize()
            logger.info(f"Récupération de tous les labels pour {manufacturer_key}")
            diagnoses = await self.engine.find_one(
                DiagnosesCollection, 
                {"manufacturer_diagnoses": {"$exists": True}, f"manufacturer_diagnoses.{manufacturer_key}": {"$exists": True}}
            )
            logger.info(f"Labels trouvés pour {manufacturer}: {diagnoses}")
            labels = diagnoses.manufacturer_diagnoses[manufacturer_key]
            return labels
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de tous les labels: {str(e)}")
            return []
        

    async def update_diagnosis(self, manufacturer: Manufacturer, diagnosis: str, labels: List[str]) -> bool:
        """
        Met à jour les labels d'un diagnostic spécifique pour un fabricant.
        Vérifie que le fabricant existe et que les labels sont bien stockés en liste.
        """
        try:
            manufacturer_key = manufacturer.value.capitalize()  # Assurer la cohérence avec MongoDB
            logging.info(f"🔄 Mise à jour du diagnostic '{diagnosis}' pour {manufacturer_key} avec labels: {labels}")
            
            logging.info(f"type des labels: {type(labels)}")
            logging.info(f"labels: {labels}")

            # 🔥 Vérifier si un document `DiagnosesCollection` existe
            diagnosis_doc = await self.engine.find_one(DiagnosesCollection)

            if not diagnosis_doc:
                logging.warning(f"⚠️ Aucun document 'manufacturer_diagnoses' trouvé en base !")
                raise HTTPException(status_code=404, detail="No diagnoses document found in database.")

            # ❌ Vérifier si le fabricant existe dans `manufacturer_diagnoses`
            if manufacturer_key not in diagnosis_doc.manufacturer_diagnoses:
                logging.error(f"❌ Manufacturer '{manufacturer_key}' not found. Check for spelling errors and case sensitivity.")
                raise HTTPException(status_code=404, detail="Manufacturer not found, check for spelling errors and case.")

            # ✅ Vérifier et convertir les labels en liste si nécessaire
            if isinstance(labels, str):
                labels = [label.strip() for label in labels.split(",")]

            # ✅ Mise à jour **directe** de l’objet en mémoire
            diagnosis_doc.manufacturer_diagnoses[manufacturer_key][diagnosis] = labels

            # 🔄 **Sauvegarde complète de l’objet**
            await self.engine.save(diagnosis_doc)

            logging.info(f"✅ Labels mis à jour pour {manufacturer_key} - {diagnosis}: {labels}")
            return True

        except HTTPException as http_error:
            raise http_error  # Laisser FastAPI gérer l'exception
        except Exception as e:
            logging.error(f"❌ Erreur lors de la mise à jour des diagnostics: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")