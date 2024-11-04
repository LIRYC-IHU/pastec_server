"""
Episodes router
Contains most of the important routes of the application

JD 31/10/24
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, Body
from fastapi.responses import JSONResponse, FileResponse
from auth import get_user_info, check_role
from schemas import User
from db import engine, Episode, Annotation, EpisodeInfo
from typing import List, Annotated
from odmantic import ObjectId


router = APIRouter()


"""
EPISODE INFO
"""

@router.get("/")
async def list_episodes(user: Annotated[User, Depends(get_user_info)], 
                        limit: int = 20
                        ) -> List[EpisodeInfo]:
    """
    List all the episodes that we have, potentially matching some criteria 
    """
    # TODO: add filters
    episodes = await engine.find(Episode, limit=limit)
    return [EpisodeInfo(**e.model_dump()) for e in episodes]



@router.put("/", response_description="Add new episode", response_model=EpisodeInfo, status_code=201, response_model_by_alias=False,)
async def add_episode(episode: Episode, user: Annotated[User, Depends(get_user_info)]):
    """
    Insert a new episode.
    A unique `id` will be created and provided in the response.
    """
    await engine.save(episode)
    return EpisodeInfo(**episode.model_dump())


@router.get("/{id}")
async def get_episode_by_id(id: ObjectId, user: Annotated[User, Depends(get_user_info)]) -> EpisodeInfo:
    """ 
    Get info about a given episode from its `id`
    """
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    return EpisodeInfo(**episode.model_dump())


@router.delete("/{id}")
async def delete_episode_by_id(id: ObjectId, user: Annotated[User, Depends(get_user_info)]) -> EpisodeInfo:
    episode = await engine.find_one(Episode, Episode.id == id)
    if episode is None:
        raise HTTPException(404, 'Episode not found for this id.')
    await engine.delete(episode)
    return EpisodeInfo(**episode.model_dump())


""" 
EPISODE EGM 
"""

@router.get("/{episode_id}/egm")
async def get_episode_egm(episode_id: str, user: Annotated[User, Depends(get_user_info)]) -> FileResponse:
    """ Get egm of the episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    if egm_not_found:
        raise HTTPException(404, detail='No EGM stored for this episode.')
    
    return episode


@router.post("/{episode_id}/egm", status_code=201)
def post_episode_egm(episode_id: ObjectId, egm: UploadFile, user: Annotated[User, Depends(get_user_info)]):
    """ Store EGM of the episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    if egm_already_exists:
        raise HTTPException(409, detail='EGM already stored for this episode.')
    
    return egm_id


@router.post("/{episode_id}/annotation")
def post_episode_label(episode_id: ObjectId, annotation: Annotation, user: Annotated[User, Depends(get_user_info)]) -> str:
    """ Save a new annotation for an episode """
    raise NotImplementedError
    if episode_not_found:
        raise HTTPException(404, detail='No episode with this ID.')
    
    return label_id



