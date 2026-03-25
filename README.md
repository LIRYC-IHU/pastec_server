# PASTEC Backend API

## Overview

The PASTEC backend is a FastAPI application that centralizes:

- episode and EGM storage
- clinical annotation workflows
- Keycloak-based authentication
- center and project access control
- AI job orchestration

It is designed for multicenter academic deployments. Most centers can join the hosted academic instance; self-hosting is mainly intended for institutions with local IT support.

## Main Capabilities

- JWT validation against Keycloak
- center-aware and project-aware RBAC
- client-side pseudonymization enforcement through center pepper verification
- storage of episode metadata, annotations, AI jobs, and EGM payloads
- manufacturer support for Medtronic, Biotronik, Boston Scientific, Abbott, and MicroPort

## Architecture

```text
Chrome Extension / Web App
          |
          v
      FastAPI API
      /        \
     v          v
 MongoDB     Keycloak
     |
     v
 AI Worker
```

## Quick Start

### Prerequisites

- Docker with Docker Compose
- a Keycloak realm for PASTEC
- MongoDB and PostgreSQL storage available through Compose

### Production deployment

1. Clone the repository.
2. Create the production environment file:

```bash
cp .env.example .env.prod
```

3. Fill in the required values in `.env.prod`.
4. Start the stack with the env file explicitly:

```bash
docker compose --env-file .env.prod up -d
```

5. Check that the API is reachable:

```bash
curl http://localhost:8000/docs
```

### Development deployment

```bash
cp .env.example .env.dev
docker compose -f docker-compose-dev.yml --env-file .env.dev up
```

### Why `--env-file` is required

The compose files use `${VAR}` interpolation for some service settings such as the Keycloak PostgreSQL password. That interpolation is resolved by Docker Compose before the container starts, so `env_file:` inside the service is not enough on its own. Use `--env-file .env.dev` or `--env-file .env.prod` when starting the stack.

## Authentication and Access Control

### Keycloak

The backend validates bearer tokens issued by Keycloak and builds a normalized access model from token claims.

Recommended client structure:

- `pastec_server`: backend client
- `pastec_plugin_dev`: unpacked Chrome extension client
- `pastec_plugin_prod`: production Chrome Web Store client

The extension clients are public PKCE clients. The backend/admin clients may remain confidential if you use client secrets for administrative operations.

### Recommended access model

- functional permissions as roles: `doctor`, `nurse`, `expert`, `pastec-admin`
- data scope as groups:
  - `/centers/bordeaux`
  - `/projects/afib-study`
- default center as the user attribute `primary_center`

The backend extracts:

- `roles`
- `centers`
- `projects`
- `primary_center`
- `user_type`

and uses them to restrict read and write access.

## Center Pepper and Provisioning

Each center uses one long-lived pepper for pseudonymization continuity.

Current flow:

1. an admin creates the center pepper once with `POST /users/centers/{center}/pepper`
2. the backend stores only the pepper hash in MongoDB
3. the backend signs and returns a center configuration bundle
4. the local admin downloads and backs up that bundle
5. end users import the signed bundle into the plugin

During uploads, the backend checks:

- the authenticated user's allowed center scope
- the `X-PASTEC-Center` header
- the `X-PASTEC-Pepper-Fingerprint` header

This prevents uploads for a center when the locally installed pepper does not match the registered pepper hash.

### Important operational rule

The bundle is critical. Losing the only valid local copy means losing the original center pepper for future consistent pseudonymization.

## Bundle Signing Keys

The backend needs a signing key pair to issue center bundles:

- `CONFIG_BUNDLE_SIGNING_PRIVATE_KEY`
- optionally `CONFIG_BUNDLE_SIGNING_PUBLIC_KEY`

In `.env` files, store PEM keys as single-line values with escaped newlines, for example:

```env
CONFIG_BUNDLE_SIGNING_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
```

The backend normalizes that format at runtime.

## Main API Areas

- `POST /episode/upload_episode`
- `POST /episode/{episode_id}/egm`
- `PUT /episode/{episode_id}/annotation`
- `GET /episode/diagnoses_labels/{manufacturer}`
- `GET /ai/jobs`
- `GET /users/me/access`
- `POST /users/centers/{center}/pepper`
- `GET /users/config-bundle/public-key`

Interactive docs are available at:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Data Storage

- MongoDB stores episodes, annotations, jobs, diagnoses, and center pepper hashes
- PostgreSQL stores Keycloak data

The backend does not store reversible patient identifiers and does not keep recoverable center peppers after bundle generation.

## Related Files

- [ENV_VARIABLES.md](./ENV_VARIABLES.md)
- [docker-compose.yml](./docker-compose.yml)
- [docker-compose-dev.yml](./docker-compose-dev.yml)
- [Chrome extension README](../chrome_ext/README.md)

## License

See [LICENSE.md](./LICENSE.md).
