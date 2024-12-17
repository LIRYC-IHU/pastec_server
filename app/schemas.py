from pydantic import BaseModel, ConfigDict, BeforeValidator, Field, PrivateAttr
from typing import List, Optional, Dict, Any, Annotated
from db import Manufacturer, Annotation
from bson import Binary

PyObjectId = Annotated[str, BeforeValidator(str)]


''' Data models for the application '''
class TokenData(BaseModel):
    username: Optional[str] = None
    token: Optional[str] = None
    role: str

class User(BaseModel):
    id: str
    username: str
    email: str
    first_name: str
    last_name: str
    realm_roles: list
    client_roles: list

class AIModel(BaseModel):
    client_id: str
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

'''Response models for Swagger auto documentation'''

class EpisodeResponse(BaseModel):
    episode_id: str
    patient_id: str
    manufacturer: Manufacturer
    episode_type: str
    labels: Dict[str, List[str]]
    exists: bool
    annotated: bool
    ai_available: bool
    ai_clients: Optional[List[str]] = None
    jobs: Optional[List[str]] = None

class EgmResponse(BaseModel):
    egm: Binary

class JobResponse(BaseModel):
    job_id: str
    id_model: str
    status: str
    created_at: str
    updated_at: str
    annotation: Optional[str]
    confidence: Optional[float]
    details: Optional[Dict]