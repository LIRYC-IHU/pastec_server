from pydantic import BaseModel
from typing import List, Optional, Dict, Any


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

class EpisodeInfo(BaseModel):
    patient_id: str
    manufacturer: str
    episode_type: str


class Episode(EpisodeInfo):
    episode_id: str
    egm_id: Optional[str]


class LabelInfo(BaseModel):
    user: str
    user_role: str
    date_time: str
    value: str
    details: Optional[Dict[str, Any]]

class Label(LabelInfo):
    label_id: str
    episode_id: str
