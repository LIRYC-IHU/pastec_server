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

The PASTEC server centralizes frontend authentication, mongoDB entries, and sends tasks to the `AI Worker`server for automatic analysis. It is based on fastAPI, with Pydantic based model validation. Data is stored on a mongoDB dabatase (See below)

## Data models


## Main routes



