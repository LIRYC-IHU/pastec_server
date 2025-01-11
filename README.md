# PASTEC SERVER
This repository contains the backend of the PASTEC project.

## PASTEC project overview
The data flows between the different components of the PASTEC project are presented in the following diagram:
![image info](./docs/architecture.drawio.svg)

The central part of this diagram is the PASTEC server.

The PASTEC server is a FastAPI application, running with a MongoDB database. User management rights are handled using a keycloak instance.

## Setting up
You will need to create a keycloak realm called `pastec` with a client called `pastec_server`. This will allow the identification of users on the system.

App-mediated access operates via Keycloak admin API, and needs to add an admin user, in this test named `pastec-admin`.

# The PASTEC SERVER - FastAPI app

The PASTEC server centralizes frontend authentication, mongoDB entries, and sends tasks to the `AI Worker` server for automatic analysis. It is based on FastAPI, with Pydantic-based model validation. Data is stored on a MongoDB database (See below).

## Data models

### ODMantic Models

- **UserType**: Enumeration of user types (EXPERT, MD, ARC, AI).
- **Manufacturer**: Enumeration of manufacturers (ABBOTT, BIOTRONIK, BOSTON, MEDTRONIC, MICROPORT).
- **Annotation**: Embedded model representing an annotation with a user, a user type, a label, and optional details.
- **JobStatus**: Enumeration of job statuses (PENDING, IN_PROGRESS, COMPLETED, FAILED).
- **Job**: Model representing a job with a job ID, episode ID, model ID, status, timestamps, annotation, confidence, and optional details.
- **Episode**: Model representing an episode with an episode ID, patient ID, manufacturer, episode type, age at episode, episode duration, optional EGM data, and a list of annotations.
- **DiagnosesCollection**: Model representing a collection of diagnoses by manufacturer and episode type.

### Pydantic Models

- **TokenData**: Model representing token data with a username, token, and role.
- **User**: Model representing a user with an ID, username, email, first name, last name, realm roles, and client roles.
- **AIModel**: Model representing an AI model with a client ID.
- **AIJob**: Model representing an AI job with a job ID, model ID, annotation, optional confidence, and optional details.
- **EpisodeInfo**: Model representing episode information with an ID, patient ID, manufacturer, episode type, and a list of annotations.

The implementation of each model in each route needs further improvement but works.

## Main routes

### Authentication routes

The authentication routes handle both human user authentication and application authentication using Keycloak.

#### Human User Authentication

- **OAuth2 Authorization Code Flow**: This flow is used for human users to authenticate via Keycloak. The `OAuth2AuthorizationCodeBearer` scheme is used to handle the authorization code flow.
- **Token Decoding and Validation**: The `decode_token` function decodes and validates the token received from Keycloak. It fetches the public key from the JWKS endpoint to verify the token's signature.
- **User Info Extraction**: The `get_user_info` function extracts user information from the token payload, including user ID, username, email, first name, last name, realm roles, and client roles.
- **Role Check**: The `check_role` dependency checks if the authenticated user has the required role to access certain routes.

##### Routes

- **GET /users/roles**: Returns the realm roles and client roles of the authenticated user.
- **POST /users/login**: Authenticates a user with a username and password, returning an access token and a refresh token.
- **POST /users/token/refresh**: Refreshes the access token using a refresh token.

#### Application Authentication

- **OAuth2 Password Flow**: This flow is used for applications to authenticate via Keycloak. The `OAuth2PasswordBearer` scheme is used to handle the password flow.
- **Application Info Extraction**: The `get_ai_model_info` function extracts application information from the token payload, specifically the client ID.

#### Combined Authentication

- **Combined Authentication Info**: The `get_auth_info` function determines whether the token belongs to a human user or an application and returns the appropriate information.

#### Token Management

- **Token with Credentials**: The `get_token_with_credentials` function retrieves a token using a username and password.
- **Refresh Token**: The `get_refresh_token` function refreshes the token using a refresh token.

## Main episode management routes

The episode management routes handle the uploading and retrieval of episode data, including EGM (Electrogram) data.

#### Routes

- **POST /episodes/upload**: Uploads a new episode to the database.
  - **Request Body**: 
    - `episode_id` (str): The unique identifier for the episode.
    - `patient_id` (str): The unique identifier for the patient.
    - `manufacturer` (Manufacturer): The manufacturer of the device.
    - `episode_type` (str): The type of episode.
    - `age_at_episode` (int): The age of the patient at the time of the episode.
    - `episode_duration` (str): The duration of the episode.
    - `annotations` (List[Annotation], optional): A list of annotations for the episode.
  - **Response**: 
    - `status` (str): The status of the upload operation.
    - `episode_id` (str): The unique identifier for the uploaded episode.

- **POST /episodes/{episode_id}/upload_egm**: Uploads EGM data for a specific episode.
  - **Path Parameter**: 
    - `episode_id` (str): The unique identifier for the episode.
  - **Request Body**: 
    - `egm` (bytes): The EGM data to be uploaded.
  - **Response**: 
    - `status` (str): The status of the upload operation.
    - `episode_id` (str): The unique identifier for the episode.

- **GET /episodes/{episode_id}/egm**: Retrieves the EGM data for a specific episode.
  - **Path Parameter**: 
    - `episode_id` (str): The unique identifier for the episode.
  - **Response**: 
    - `egm` (bytes): The EGM data for the episode.

These routes ensure that episode data, including EGM data, can be efficiently uploaded and retrieved from the database, facilitating further analysis and processing by the AI Worker.

This part allows the PASTEC Server to seamlessly get and post data to the frontend, setting up a complete, anonimized database as well. 

## AI handling routes

These routes are meant to handle the jobs sent to the AI server. This allows the AI server to retrieve only the relevant information during the time when it's needed (i.e., while the job is open) and close it afterward to protect the data.

#### Routes

- **POST /ai/{episode_id}/ai**: Sends a job to the AI models for analysis.
  - **Path Parameter**: 
    - `episode_id` (str): The unique identifier for the episode.
  - **Request Body**: 
    - `ai_clients` (List[str]): A list of AI clients to which the job should be sent.
  - **Response**: 
    - `message` (str): A message indicating the status of the request.
    - `jobs` (List[Dict]): A list of jobs created, each containing the job ID, model ID, and status.

All the routes interacting with the AI server use a job system to update the work and get the data, to protect the episode ids and all sensitive data non relevant to the automatic analysis. This serves as a way to check the advancement of AI tasks from the frontend as well

- **GET /ai/{job_id}/egm**: Retrieves the EGM data for a specific job.
  - **Path Parameter**: 
    - `job_id` (str): The unique identifier for the job.
  - **Response**: 
    - `FileResponse`: The EGM data file for the job.

- **PUT /ai/{job_id}/annotation**: Adds an AI annotation to the database for a specific job.
  - **Path Parameter**: 
    - `job_id` (str): The unique identifier for the job.
  - **Request Body**: 
    - `ai_job` (AIJob): The AI job details, including the annotation, confidence, and optional details.
  - **Response**: 
    - `message` (str): A message indicating the status of the request.
    - `episode_id` (str): The unique identifier for the episode.
    - `annotation` (Dict): The details of the added annotation.
    - `job_id` (str): The unique identifier for the job.
    - `status` (str): The status of the job.

- **GET /ai/jobs**: Retrieves the status of a specific job.
  - **Query Parameter**: 
    - `job_id` (str): The unique identifier for the job.
  - **Response**: 
    - `job_id` (str): The unique identifier for the job.
    - `job_annotation` (str): The annotation of the job.
    - `id_model` (str): The model ID used for the job.
    - `status` (str): The status of the job.
    - `created_at` (str): The creation timestamp of the job.
    - `updated_at` (str): The last updated timestamp of the job.

These routes ensure that AI jobs can be efficiently managed, including sending jobs for analysis, retrieving EGM data, adding annotations, and checking job statuses.

# The AI Worker server

This server is separated from the original one to allow independent deployment and development. It contains AI models with predetermined episode types targets defined in Keycloak.

## Prerequisites

Each new model needs to come with its dependencies to allow proper deployment. AF Boston classifier is based upon `tensorflow==2.17.0`, `keras==3.4.1`, `librosa>=0.9.0` and `numpy==1.23.0` in order to work properly. To have a proper idea of the dependencies needed, use the command `pip freeze -r` to check dependencies of your environment.

## Define a new model inside Keycloak

Each model is registered as an individual client, which name must be the same as in the `.py` file used to call the model. 

To register a model:
- log in with an admin account to Keycloak (http://localhost:8080)
- create a client with authentication rule 













