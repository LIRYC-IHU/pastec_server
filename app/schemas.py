from pydantic import BaseModel, ConfigDict, BeforeValidator, Field, PrivateAttr
from typing import List, Optional, Dict, Any, Annotated
from db import Manufacturer, Annotation

PyObjectId = Annotated[str, BeforeValidator(str)]

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

class Label(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, 
        arbitrary_types_allowed=True,
        json_schema_extra={"example": { "episode_id": "1234", "user_id": "josselin", "user_role": "md", "value": "AF"}}
        )
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    episode_id: str = Field(...)
    user_id: str = Field(...)
    user_role: str = Field(...)
    value: str = Field(...)
    details: Optional[Dict[str, Any]]
    _db_collection: str = PrivateAttr('labels')

class EpisodeInfo(BaseModel):
    id: str
    patient_id: str
    manufacturer: Manufacturer
    episode_type: str
    annotations: List[Annotation] = []
    
    @property
    def labels(self) -> List[str]:
        return [a.label for a in self.annotations]

