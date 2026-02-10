## setup for a grapiql interface to allow easy querying of the database

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from fastapi.params import Query
from typing import Optional, List
from db import engine, Episode, Annotation
from odmantic.bson import Binary
import graphene
from graphene_mongo import MongoengineObjectType

class BinaryScalar(Scalar):
    """Scalaire pour représenter les données binaires"""
    
    @staticmethod
    def serialize(binary):
        # Conversion de Binary en string base64 pour GraphQL
        if isinstance(binary, Binary):
            import base64
            return base64.b64encode(binary).decode('utf-8')
        return str(binary)
    
    @staticmethod
    def parse_literal(node):
        # Conversion depuis une requête GraphQL
        import base64
        return Binary(base64.b64decode(node.value))
    
    @staticmethod
    def parse_value(value):
        # Conversion depuis une variable GraphQL
        import base64
        return Binary(base64.b64decode(value))

class EpisodeSBType(graphene.ObjectType):
    class Meta:
        interfaces = (graphene.relay.Node,)
    
    episode_id = graphene.String()
    patient_id = graphene.String()
    # ...autres champs...
    
    # Remplacer le champ qui utilise Binary par votre scalaire personnalisé
    egm_data = BinaryScalar()

@strawberry.type
class EpisodeSearch():
   episode_type: str

@strawberry.experimental.pydantic.type(model=Annotation, all_fields=True)
class Annotation:
    pass

@strawberry.experimental.pydantic.type(model=Episode, all_fields=True)
class EpisodeSB:
    pass

async def episodes(episode_type: str) -> List[EpisodeSB]:
    """
    Récupère une liste d'épisodes avec pagination.
    """
    episodes = await engine.find(EpisodeSB, EpisodeSB.episode_type==episode_type)
    return [EpisodeSB.from_pydantic(ep) for ep in episodes]

@strawberry.type
class Query:
    episode: EpisodeSB = strawberry.field(resolver=episodes)


schema = strawberry.Schema(query=Query)
