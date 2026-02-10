import os
import logging

logger = logging.getLogger('uvicorn.error')

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI')
if not MONGODB_URI:
    raise ValueError("MONGODB_URI must be set in environment variables")

MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME')
if not MONGODB_DB_NAME:
    raise ValueError("MONGODB_DB_NAME must be set in environment variables")

AI_WORKER_URL = os.getenv('AI_WORKER_URL')
if not AI_WORKER_URL:
    raise ValueError("AI_WORKER_URL must be set in environment variables")

# Keycloak Configuration
KEYCLOAK_SERVER_URL = os.getenv('KEYCLOAK_SERVER_URL')
if not KEYCLOAK_SERVER_URL:
    raise ValueError("KEYCLOAK_SERVER_URL must be set in environment variables")

KEYCLOAK_INTERNAL_SERVER_URL = os.getenv('KEYCLOAK_INTERNAL_SERVER_URL')
if not KEYCLOAK_INTERNAL_SERVER_URL:
    raise ValueError("KEYCLOAK_INTERNAL_SERVER_URL must be set in environment variables")

KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM')
if not KEYCLOAK_REALM:
    raise ValueError("KEYCLOAK_REALM must be set in environment variables")

KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID')
if not KEYCLOAK_CLIENT_ID:
    raise ValueError("KEYCLOAK_CLIENT_ID must be set in environment variables")

KEYCLOAK_CLIENT_SECRET = os.getenv('KEYCLOAK_CLIENT_SECRET')
if not KEYCLOAK_CLIENT_SECRET:
    raise ValueError("KEYCLOAK_CLIENT_SECRET must be set in environment variables")

KEYCLOAK_ADMIN_CLIENT_SECRET = os.getenv('KEYCLOAK_ADMIN_CLIENT_SECRET')
if not KEYCLOAK_ADMIN_CLIENT_SECRET:
    raise ValueError("KEYCLOAK_ADMIN_CLIENT_SECRET must be set in environment variables")

KEYCLOAK_PASTEC_ADMIN = os.getenv('KEYCLOAK_PASTEC_ADMIN')
if not KEYCLOAK_PASTEC_ADMIN:
    raise ValueError("KEYCLOAK_PASTEC_ADMIN must be set in environment variables")

KEYCLOAK_PASTEC_ADMIN_PASSWORD = os.getenv('KEYCLOAK_PASTEC_ADMIN_PASSWORD')
if not KEYCLOAK_PASTEC_ADMIN_PASSWORD:
    raise ValueError("KEYCLOAK_PASTEC_ADMIN_PASSWORD must be set in environment variables")

# Keycloak Endpoints
KEYCLOAK_OPENID_CONNECT_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration/"
KEYCLOAK_TOKEN_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token/"
KEYCLOAK_AUTH_URL = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth/"
KEYCLOAK_INTERNAL_REALM_URL = f"{KEYCLOAK_INTERNAL_SERVER_URL}/realms/{KEYCLOAK_REALM}/"