# PASTEC SERVER
This repository contains the backend of the PASTEC project.

## PASTEC project overview
The data flows between the different components of the PASTEC project are presented in the following diagram:
![image info](./docs/architecture.drawio.svg)

The central part of this diagram is the PASTEC server.

The PASTEC server is a FastAPI application, running with a MongoDB database. User management rights are handled using a keycloak instance.

