""" 
Object document model

J Duchateau 04/11/24
"""

from odmantic import AIOEngine, Field, Model, EmbeddedModel, ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from settings import MONGODB_URI, MONGODB_DB_NAME
from typing import List, Optional, Dict
from pydantic import BaseModel, computed_field
from enum import Enum
from bson import Binary

client = AsyncIOMotorClient(MONGODB_URI)
engine = AIOEngine(client, database=MONGODB_DB_NAME)

class UserType(str, Enum):
    EXPERT = "expert"
    MD = "md"
    ARC = "arc"
    AI = "ai"

class Manufacturer(str, Enum):
    ABBOTT = "abbott"
    BIOTRONIK = "biotronik"
    BOSTON = "boston"
    MEDTRONIC = "medtronic"
    MICROPORT = "microport"
    
class Annotation(EmbeddedModel):
    user: str
    user_type: UserType
    label: str  # This is the main label
    details: Optional[dict]  # Contains potential additional information

class Episode(Model):
    episode_id: str = Field(primary_field=True)  # L'ID généré par le frontend devient l'identifiant principal
    patient_id: str = Field(index=True)
    manufacturer: Manufacturer
    episode_type: str
    age_at_episode: int
    episode_duration: int
    egm: Optional[Binary] = None
    annotations: List[Annotation] = []
    
    model_config = {
        "collection": "episodes",
        "json_schema_extra": {
            "example": {
                "episode_id": "hash_generated_by_frontend",
                "patient_id": "patient_hash",
                "manufacturer": "boston",
                "episode_type": "AT",
                "age_at_episode": 65,
                "episode_duration": 30,
                "annotations": []
            }
        }
    }

    @computed_field
    @property
    def num_annotations(self) -> int:
        return len(self.annotations)

class EpisodeInfo(BaseModel):
    id: str
    patient_id: str = Field(index=True)
    manufacturer: Manufacturer
    episode_type: str
    annotations: List[Annotation] = []
    @computed_field
    @property
    def labels(self) -> List[str]:
        return [a.label for a in self.annotations]
    
class Diagnosis(BaseModel):
    """
    Structure simplifiée pour un diagnostic
    """
    possible_diagnoses: List[str]

class DiagnosesCollection(Model):
    """
    Structure simplifiée:
    {
        "manufacturer_diagnoses": {
            "abbott": {
                "AT": ["diagnostic1", "diagnostic2"],
                "VT": ["diagnostic1", "diagnostic2"]
            }
        }
    }
    """
    manufacturer_diagnoses: Dict[str, Dict[str, List[str]]]

    model_config = {
        "collection": "diagnoses"
    }
    
    