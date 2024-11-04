""" 
Object document model

J Duchateau 04/11/24
"""
from odmantic import AIOEngine, Field, Model, EmbeddedModel, ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from settings import MONGODB_URI, MONGODB_DB_NAME
from typing import List, Optional
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
    details: dict  # Contains potential additional information


class Episode(Model):
    patient_id: str = Field(index=True)
    manufacturer: Manufacturer
    episode_type: str
    egm: Optional[Binary] = None
    annotations: List[Annotation] = []

    @computed_field
    @property
    def num_annotations(self) -> int:
        return len(self.annotations)


class EpisodeInfo(BaseModel):
    id: ObjectId
    patient_id: str = Field(index=True)
    manufacturer: Manufacturer
    episode_type: str
    num_annotations: int

