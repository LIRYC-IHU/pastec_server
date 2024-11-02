from settings import MONGODB_URI
from pymongo import MongoClient

# Mongo DB client
mongo_client = MongoClient(MONGODB_URI)
