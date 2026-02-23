# PASTEC Backend - Deployment Guide

## Docker Deployment

### Overview

The PASTEC backend uses a multi-container Docker setup for production deployment.

**Services:**
- `fastapi-app` - Main API server (4 Gunicorn workers with Uvicorn)
- `mongodb` - NoSQL database for episode storage
- `keycloak` - Authentication and authorization server
- `postgres` - Keycloak's database
- `ai-worker` - AI processing worker (optional)

### Docker Compose Configuration

The project includes two main compose files:
- `docker-compose.yml` - Production configuration
- `docker-compose-dev.yml` - Development configuration

### Production Deployment

1. **Prepare environment**
   ```bash
   cp .env.example .env.prod
   # Edit .env.prod with production values
   ```

2. **Build images**
   ```bash
   docker-compose build
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Verify deployment**
   ```bash
   # Check all services are running
   docker-compose ps
   
   # Check logs
   docker-compose logs -f fastapi-app
   ```

5. **Test API**
   ```bash
   curl http://localhost:8000/docs
   ```

### Service Details

#### FastAPI App

```yaml
fastapi-app:
  build:
    context: ./app
    dockerfile: Dockerfile
  ports:
    - "8000:8000"
  command: >
    gunicorn main:app
    -k uvicorn.workers.UvicornWorker
    -w 4
    -b 0.0.0.0:8000
    --timeout 120
  env_file:
    - .env.prod
  depends_on:
    - mongodb
    - keycloak
  restart: unless-stopped
```

**Configuration:**
- 4 Gunicorn workers (configurable via `WEB_CONCURRENCY`)
- 120s request timeout
- Health checks every 30s
- Auto-restart on failure

#### MongoDB

```yaml
mongodb:
  image: mongo:latest
  volumes:
    - ./data/mongo:/data/db
  env_file:
    - .env.prod
  restart: unless-stopped
```

**Configuration:**
- Data persisted to `./data/mongo`
- Configured via environment variables
- No external port exposure (internal only)

#### Keycloak

```yaml
keycloak:
  image: quay.io/keycloak/keycloak:22.0
  command: start-dev
  ports:
    - "8084:8080"
  env_file:
    - .env.prod
  depends_on:
    - postgres
  restart: unless-stopped
```

**Configuration:**
- Exposed on port 8084
- Uses PostgreSQL for persistence
- Development mode for initial setup
- Switch to `start` for production

#### PostgreSQL (Keycloak DB)

```yaml
postgres:
  image: postgres:15
  volumes:
    - ./docker/postgres:/var/lib/postgresql/data
  env_file:
    - .env.prod
  restart: unless-stopped
```

### Container Management

#### Start Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d fastapi-app

# Start with rebuild
docker-compose up -d --build
```

#### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (DELETES ALL DATA)
docker-compose down -v

# Stop specific service
docker-compose stop fastapi-app
```

#### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi-app

# Last 100 lines
docker-compose logs --tail=100 fastapi-app
```

#### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart fastapi-app
```

### Health Checks

#### API Health

```bash
# Check API is responding
curl http://localhost:8000/docs

# Check specific endpoint
curl http://localhost:8000/episode/diagnoses_labels/Medtronic
```

#### MongoDB Health

```bash
# Connect to MongoDB shell
docker-compose exec mongodb mongosh

# Check database status
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Check collections
docker-compose exec mongodb mongosh pastec_db --eval "db.getCollectionNames()"
```

#### Keycloak Health

```bash
# Check Keycloak is accessible
curl http://localhost:8084/realms/pastec

# Access admin console
open http://localhost:8084/admin/
```

### Scaling

#### Scale API Workers

```bash
# Scale to 3 instances
docker-compose up -d --scale fastapi-app=3

# Or modify docker-compose.yml
services:
  fastapi-app:
    deploy:
      replicas: 3
```

#### Adjust Gunicorn Workers

In `.env.prod`:
```bash
WEB_CONCURRENCY=8  # 8 workers per container
```

### Backup and Restore

#### MongoDB Backup

```bash
# Create backup
docker-compose exec mongodb mongodump --out=/data/backup

# Copy to host
docker cp mongodb:/data/backup ./backup_$(date +%Y%m%d)
```

#### MongoDB Restore

```bash
# Copy backup to container
docker cp ./backup_20260217 mongodb:/data/restore

# Restore
docker-compose exec mongodb mongorestore /data/restore
```

#### PostgreSQL Backup (Keycloak)

```bash
# Backup
docker-compose exec postgres pg_dump -U keycloak keycloak > keycloak_backup.sql

# Restore
docker-compose exec -T postgres psql -U keycloak keycloak < keycloak_backup.sql
```

### Monitoring

#### Resource Usage

```bash
# Check container stats
docker stats

# Check specific container
docker stats fastapi
```

#### Disk Usage

```bash
# Check volumes
docker system df -v

# Check MongoDB data
du -sh ./data/mongo

# Check PostgreSQL data
du -sh ./docker/postgres
```

### Troubleshooting

#### Container Won't Start

```bash
# Check logs
docker-compose logs fastapi-app

# Check configuration
docker-compose config

# Rebuild
docker-compose build --no-cache fastapi-app
docker-compose up -d fastapi-app
```

#### MongoDB Connection Issues

```bash
# Check MongoDB is running
docker-compose ps mongodb

# Check MongoDB logs
docker-compose logs mongodb

# Test connection
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Verify credentials in .env.prod
cat .env.prod | grep MONGODB
```

#### Keycloak Issues

```bash
# Check Keycloak logs
docker-compose logs keycloak

# Verify PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Reset Keycloak admin password
docker-compose exec keycloak /opt/keycloak/bin/kcadm.sh set-password \
  --username admin \
  --new-password newpassword
```

#### API Response Timeout

```bash
# Increase Gunicorn timeout in docker-compose.yml
command: >
  gunicorn main:app
  ...
  --timeout 180  # Increase to 180s

# Or via environment variable
GUNICORN_TIMEOUT=180
```

#### Out of Memory

```bash
# Check memory usage
docker stats

# Reduce number of workers
WEB_CONCURRENCY=2  # in .env.prod

# Or add memory limits in docker-compose.yml
services:
  fastapi-app:
    mem_limit: 2g
    memswap_limit: 2g
```

### Production Best Practices

1. **Use production mode for Keycloak**
   ```yaml
   keycloak:
     command: start  # Instead of start-dev
   ```

2. **Enable HTTPS**
   - Use a reverse proxy (Nginx, Traefik)
   - Configure SSL certificates
   - Update KEYCLOAK_SERVER_URL to use https://

3. **Secure MongoDB**
   - Enable authentication
   - Use strong passwords
   - Don't expose MongoDB port externally

4. **Backup regularly**
   - Schedule automated backups
   - Test restore procedures
   - Store backups off-site

5. **Monitor logs**
   - Use log aggregation (ELK, Loki)
   - Set up alerts for errors
   - Rotate logs regularly

6. **Update regularly**
   - Keep Docker images updated
   - Monitor security advisories
   - Test updates in staging first

### Environment-Specific Configurations

#### Development

```bash
# Use docker-compose-dev.yml
docker-compose -f docker-compose-dev.yml up -d

# Characteristics:
# - Hot reload enabled
# - Debug logging
# - Exposed MongoDB port
# - Test data seeding
```

#### Staging

```bash
# Use production compose with staging env
docker-compose --env-file .env.staging up -d

# Characteristics:
# - Production-like setup
# - Test credentials
# - Separate database
# - Monitoring enabled
```

#### Production

```bash
# Use production compose and env
docker-compose up -d

# Characteristics:
# - Optimized for performance
# - Security hardened
# - Backup automation
# - Full monitoring
```

### Network Configuration

#### Internal Network

All services communicate via Docker network:
```yaml
networks:
  backend-network:
    driver: bridge
```

#### External Access

Only these ports are exposed:
- `8000` - FastAPI (API)
- `8084` - Keycloak (Auth)

MongoDB and PostgreSQL are internal only.

#### Firewall Rules

```bash
# Allow API access
sudo ufw allow 8000/tcp

# Allow Keycloak access
sudo ufw allow 8084/tcp

# Block direct database access
sudo ufw deny 27017/tcp  # MongoDB
sudo ufw deny 5432/tcp   # PostgreSQL
```

### Performance Tuning

#### Gunicorn Configuration

```bash
# In docker-compose.yml
command: >
  gunicorn main:app
  -k uvicorn.workers.UvicornWorker
  -w ${WEB_CONCURRENCY:-4}  # Workers
  -b 0.0.0.0:8000
  --timeout ${GUNICORN_TIMEOUT:-120}  # Timeout
  --keep-alive 30  # Keep connections alive
  --graceful-timeout 30  # Graceful shutdown
  --max-requests 1000  # Restart workers after N requests
  --max-requests-jitter 50  # Add jitter to max-requests
```

#### MongoDB Optimization

```javascript
// Create indexes for frequently queried fields
db.episodes.createIndex({ "episode_id": 1 })
db.episodes.createIndex({ "patient_id": 1 })
db.episodes.createIndex({ "manufacturer": 1, "episode_type": 1 })
```

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build and push Docker image
        run: |
          docker build -t pastec/api:latest ./app
          docker push pastec/api:latest
      
      - name: Deploy to server
        run: |
          ssh user@server 'cd /opt/pastec && docker-compose pull && docker-compose up -d'
```

## Related Documentation

- [ENV_VARIABLES.md](./ENV_VARIABLES.md) - Complete environment variable reference
- [README.md](./README.md) - Main documentation
- [LICENSE.md](./LICENSE.md) - License information

---

**Last Updated**: February 17, 2026  
**Version**: 0.1
