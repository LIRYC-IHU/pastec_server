""" 
Object document model

J Duchateau 04/11/24
"""

from odmantic import AIOEngine, Field, Model, EmbeddedModel, ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from settings import MONGODB_URI, MONGODB_DB_NAME
from typing import List, Optional, Dict, Annotated
from pydantic import BaseModel, BeforeValidator
from enum import Enum
from bson import Binary
import datetime

PyObjectId = Annotated[str, BeforeValidator(str)]
client = AsyncIOMotorClient(MONGODB_URI)
engine = AIOEngine(client, database=MONGODB_DB_NAME)

class UserType(str, Enum):
    EXPERT = "expert"
    MD = "md"
    ARC = "nurse"
    AI_MODEL = "ai"

class Manufacturer(str, Enum):
    ABBOTT = "abbott"
    BIOTRONIK = "biotronik"
    BOSTON = "boston"
    MEDTRONIC = "medtronic"
    MICROPORT = "microport"
    
class Center(str, Enum):
    BORDEAUX = "bordeaux",
    PARIS = "paris",
    LYON = "lyon",
    MARSEILLE = "marseille",
    TOULOUSE = "toulouse",
    NANTES = "nantes",
    STRASBOURG = "strasbourg",
    LILLE = "lille",
    NICE = "nice",
    RENNES = "rennes",
    GRENOBLE = "grenoble",
    MONTPELLIER = "montpellier",
    TOURS = "tours",
    
class UserEntry(BaseModel):
    username: str = Field(..., description="Username of the user")
    password: str = Field(..., description="Password of the user")
    first_name: str = Field(..., description="First name of the user")
    last_name: str = Field(..., description="Last name of the user")
    email: str = Field(..., description="Email of the user")
    center: Center = Field(..., description="Center where the user is located")
    user_type: UserType = Field(..., description="Type of user (expert, md, nurse, ai)")
    
class Annotation(EmbeddedModel):
    user: str
    user_type: UserType
    label: str  # This is the main label
    details: Optional[dict]  # Contains potential additional information

class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Model):
    job_id: str
    episode_id: str
    id_model: str  
    status: JobStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime
    annotation: Optional[str]
    confidence: Optional[float]
    details: Optional[Dict]
    
    model_config = {
        "collection": "jobs"
    }

class Episode(Model):
    episode_id: str = Field(...)
    patient_id: str = Field(...)
    manufacturer: Manufacturer
    episode_type: str = Field(...)
    age_at_episode: int
    episode_duration: str = Field(...)
    implant_model: Optional[str] = Field(...)
    egm: Optional[Binary] = None
    annotations: List[Annotation] = []
    
    model_config = {
        "collection": "episodes"
    }
    
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

class AIJob(BaseModel):
    job_id: str
    id_model: str  # Remplacez id_model par id_model
    annotation: str
    confidence: Optional[float]
    details: Optional[Dict]

class ProcessingTimeForEpisode(Model):
    episode_id: str
    user: str
    user_type: UserType
    processing_time: float
    annotation: str
    
    model_config = {
        "collection": "processing_times"
    }

class TokenData(BaseModel):
    username: Optional[str] = None
    token: Optional[str] = None
    role: str

class Token(BaseModel):
    token: str

class User(BaseModel):
    id: str
    username: str
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    realm_roles: list
    client_roles: list
    groups: list

class AIModel(BaseModel):
    client_id: str= Field(..., description="Client ID of the AI model")
    model_name: str= Field(..., description="Name of the AI model")
    client_roles: List[str] = Field(..., description="Client Roles associated with the AI model")
    realm_roles: List[str] = Field(..., description="Service Account Roles associated with the AI model")
    
    ''' A compléter '''

class AIJob(BaseModel):
    job_id: str
    id_model: str
    annotation: str
    confidence: Optional[float]
    details: Optional[Dict]

class EpisodeInfo(BaseModel):
    id: str
    patient_id: str
    manufacturer: Manufacturer
    episode_type: str
    annotations: List[Annotation] = []
    
    @property
    def labels(self) -> List[str]:
        return [a.label for a in self.annotations]