"""
Episodes router
Contains most of the important routes of the application

JD 31/10/24
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from app.main import keycloak
from app.schemas import Episode, EpisodeInfo, Label, LabelInfo
from typing import Optional, List


router = APIRouter('episode')


"""
EPISODE INFO
"""

@router.get("/")
def list_episodes(manufacturer: Optional[str] = None, episode_type: Optional[str] = None, patient_id: Optional[str] = None, user = Depends(keycloak.get_current_user)) -> List[Episode]:
    """ List all the episodes that we have, potentially matching some criteria """
    raise NotImplementedError

    return episodes


@router.post("/", status_code=201)
def post_episode(episode_info: EpisodeInfo, user = Depends(keycloak.get_current_user)) -> Episode:
    """ Store an episode in the DB """
    raise NotImplementedError

    if episode_already_exists:
        return JSONResponse(status_code=409,content=episode)
    
    return episode_info


@router.get("/{episode_id}")
def get_episode_info(episode_id: str, user = Depends(keycloak.get_current_user)) -> Episode:
    """ Get info about a give episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    return episode


""" 
EPISODE EGM 
"""

@router.get("/{episode_id}/egm")
def get_episode_egm(episode_id: str, user = Depends(keycloak.get_current_user)) -> FileResponse:
    """ Get egm of the episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    if egm_not_found:
        raise HTTPException(404, detail='No EGM stored for this episode.')
    
    return episode


@router.post("/{episode_id}/egm", status_code=201)
def post_episode_egm(episode_id: str, egm: UploadFile, user = Depends(keycloak.get_current_user)):
    """ Store EGM of the episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    if egm_already_exists:
        raise HTTPException(409, detail='EGM already stored for this episode.')
    
    return egm_id


"""
EPISODE LABELS
"""

@router.get("/{episode_id}/labels")
def get_episode_labels(episode_id: str, user = Depends(keycloak.get_current_user)) -> List[Label]:
    """ Get labels of a given episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    return labels


@router.post("/{episode_id}/label")
def post_episode_label(episode_id: str, label: LabelInfo, user = Depends(keycloak.get_current_user)) -> str:
    """ Get labels of a given episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    return label_id



