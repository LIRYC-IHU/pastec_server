# Variables d'Environnement - PASTEC Backend

Ce document décrit toutes les variables d'environnement nécessaires au bon fonctionnement de l'application PASTEC.

## 📋 Table des Matières

- [Configuration de Base](#configuration-de-base)
- [Keycloak (Authentification)](#keycloak-authentification)
- [Bases de Données](#bases-de-données)
- [Services AI](#services-ai)
- [Sécurité](#sécurité)
- [Fichiers de Configuration](#fichiers-de-configuration)

---

## Configuration de Base

### `APP_MODULE`
- **Description**: Module ASGI à charger pour Gunicorn
- **Valeur par défaut**: `main:app`
- **Requis**: Non (utilise la valeur par défaut)
- **Exemple**: `main:app`

### `WEB_CONCURRENCY`
- **Description**: Nombre de workers Gunicorn
- **Valeur par défaut**: `4`
- **Requis**: Non
- **Exemple**: `2` (dev), `4` (prod)
- **Note**: Ajustez selon les ressources CPU disponibles

### `GUNICORN_TIMEOUT`
- **Description**: Timeout en secondes pour les requêtes Gunicorn
- **Valeur par défaut**: `120`
- **Requis**: Non
- **Exemple**: `120`

---

## Keycloak (Authentification)

### `KEYCLOAK_SERVER_URL`
- **Description**: URL publique du serveur Keycloak (accessible depuis l'extérieur)
- **Requis**: ✅ **OUI**
- **Exemple Dev**: `http://localhost:8084`
- **Exemple Prod**: `https://pastec.ihu-liryc.fr/auth`
- **Note**: Cette URL est utilisée par les clients pour s'authentifier

### `KEYCLOAK_INTERNAL_SERVER_URL`
- **Description**: URL interne du serveur Keycloak (pour communication entre conteneurs)
- **Requis**: ✅ **OUI**
- **Exemple**: `http://keycloak:8080`
- **Note**: Utilisé pour la communication backend-to-backend

### `KEYCLOAK_REALM`
- **Description**: Nom du realm Keycloak
- **Requis**: ✅ **OUI**
- **Exemple**: `pastec`

### `KEYCLOAK_CLIENT_ID`
- **Description**: ID du client Keycloak pour l'application
- **Requis**: ✅ **OUI**
- **Exemple**: `pastec_server`

### `KEYCLOAK_CLIENT_SECRET`
- **Description**: Secret du client Keycloak
- **Requis**: ✅ **OUI - SENSIBLE** 🔒
- **Exemple**: `dsaImyh0BaQyMiLcaGwhN5ZidUqLz3Lj`
- **Note**: À générer depuis la console Keycloak. **NE JAMAIS COMMITTER**. Cette variable concerne le client backend/admin si vous utilisez un client confidentiel. Les clients Chrome `pastec_plugin_dev` et `pastec_plugin_prod` restent des clients publics PKCE et n'utilisent pas de secret.

### `KEYCLOAK_ADMIN_CLIENT_SECRET`
- **Description**: Secret du client admin Keycloak
- **Requis**: ✅ **OUI - SENSIBLE** 🔒
- **Exemple**: `DGrODPab1F5nQAS1ojAOlsMpXvUUwG8T`
- **Note**: Utilisé pour les opérations administratives si vous utilisez un client admin confidentiel. **NE JAMAIS COMMITTER**

### `KEYCLOAK_ADMIN`
- **Description**: Nom d'utilisateur de l'administrateur Keycloak
- **Requis**: ✅ **OUI**
- **Exemple**: `admin`
- **Note**: Compte super-admin Keycloak

### `KEYCLOAK_ADMIN_PASSWORD`
- **Description**: Mot de passe de l'administrateur Keycloak
- **Requis**: ✅ **OUI - SENSIBLE** 🔒
- **Exemple**: `adminpassword`
- **Note**: **NE JAMAIS COMMITTER**

### `KEYCLOAK_PASTEC_ADMIN`
- **Description**: Nom d'utilisateur de l'administrateur applicatif PASTEC
- **Requis**: ✅ **OUI**
- **Exemple**: `pastec-admin`

### `KEYCLOAK_PASTEC_ADMIN_PASSWORD`
- **Description**: Mot de passe de l'administrateur applicatif PASTEC
- **Requis**: ✅ **OUI - SENSIBLE** 🔒
- **Exemple**: `test`
- **Note**: **NE JAMAIS COMMITTER**

### `TEST_ADMIN_USERNAME` (Dev uniquement)
- **Description**: Nom d'utilisateur pour les tests en développement
- **Requis**: Non (dev uniquement)
- **Exemple**: `test_admin`

### `TEST_ADMIN_PASSWORD` (Dev uniquement)
- **Description**: Mot de passe pour les tests en développement
- **Requis**: Non (dev uniquement) - **SENSIBLE** 🔒
- **Exemple**: `test_password`

---

## Bases de Données

### MongoDB

#### `MONGODB_URI`
- **Description**: URI de connexion à MongoDB
- **Requis**: ✅ **OUI**
- **Exemple**: `mongodb://mongodb:27017/pastec_db`
- **Note**: Format: `mongodb://[host]:[port]/[database]`

#### `MONGODB_DB_NAME`
- **Description**: Nom de la base de données MongoDB
- **Requis**: ✅ **OUI**
- **Exemple**: `pastec_db`

### PostgreSQL (pour Keycloak)

#### `POSTGRES_DB`
- **Description**: Nom de la base de données PostgreSQL
- **Requis**: ✅ **OUI**
- **Exemple**: `keycloak`

#### `POSTGRES_USER`
- **Description**: Nom d'utilisateur PostgreSQL
- **Requis**: ✅ **OUI**
- **Exemple**: `keycloak`

#### `POSTGRES_PASSWORD`
- **Description**: Mot de passe PostgreSQL
- **Requis**: ✅ **OUI - SENSIBLE** 🔒
- **Exemple**: `password`
- **Note**: **NE JAMAIS COMMITTER**. Si la base PostgreSQL existe déjà, modifier cette valeur dans `.env` ne change pas automatiquement le mot de passe stocké dans PostgreSQL. Il faut aussi mettre à jour le mot de passe du rôle dans la base.

---

## Services AI

### `AI_WORKER_URL`
- **Description**: URL du service AI Worker
- **Requis**: ✅ **OUI**
- **Exemple**: `http://ai_worker:8001`
- **Note**: Utilisé pour les requêtes d'analyse IA

### `FASTAPI_URL`
- **Description**: URL du service FastAPI principal (pour communication entre services)
- **Requis**: ✅ **OUI**
- **Exemple**: `http://fastapi-app:8000`

---

## Sécurité

### `CONFIG_BUNDLE_SIGNING_PRIVATE_KEY`
- **Description**: Clé privée PEM utilisée pour signer les bundles de configuration centre remis aux utilisateurs.
- **Requis**: ✅ **OUI** si vous utilisez le provisionnement par bundle signé
- **Note**: À conserver côté backend uniquement. Le backend ne conserve pas le pepper brut après génération; il signe simplement le bundle remis une seule fois à l'admin local.
- **Format recommandé dans `.env`**: PEM sur une seule ligne avec des `\n` échappés.

### `CONFIG_BUNDLE_SIGNING_PUBLIC_KEY`
- **Description**: Clé publique PEM associée, utilisée pour exposer la clé de vérification des bundles.
- **Requis**: Non si elle peut être dérivée de la clé privée
- **Note**: Peut être fournie explicitement pour éviter toute ambiguïté opérationnelle. Même format `.env` que la clé privée.

### `AUTH_CENTER_GROUP_PREFIX`
- **Description**: Préfixe de groupe Keycloak interprété comme un rattachement centre.
- **Valeur par défaut**: `centers`
- **Exemple**: un groupe `/centers/bordeaux` donnera l'accès au centre `bordeaux`

### `AUTH_PROJECT_GROUP_PREFIX`
- **Description**: Préfixe de groupe Keycloak interprété comme un rattachement projet.
- **Valeur par défaut**: `projects`
- **Exemple**: un groupe `/projects/afib-study` donnera l'accès au projet `afib-study`

### `AUTH_CENTER_ROLE_PREFIX`
- **Description**: Préfixe de rôle interprété comme un rattachement centre.
- **Valeur par défaut**: `center:`
- **Exemple**: `center:bordeaux`

### `AUTH_PROJECT_ROLE_PREFIX`
- **Description**: Préfixe de rôle interprété comme un rattachement projet.
- **Valeur par défaut**: `project:`
- **Exemple**: `project:afib-study`

### `AUTH_GLOBAL_ACCESS_ROLES`
- **Description**: Liste de rôles séparés par des virgules qui contournent les restrictions centre/projet.
- **Valeur par défaut**: `pastec-admin`
- **Exemple**: `pastec-admin,super-reader`

### `AUTH_ALLOW_LEGACY_UNSCOPED_ACCESS`
- **Description**: Autorise temporairement l'accès aux épisodes historiques ne possédant pas encore de champ `center`.
- **Valeur par défaut**: `true`
- **Note**: Passez à `false` une fois les données historiques migrées.

---

## Fichiers de Configuration

Le projet utilise plusieurs fichiers `.env` pour gérer les configurations:

### 📄 `.env.example`
Template documenté avec toutes les variables nécessaires.  
**Ce fichier PEUT être commité** (ne contient pas de secrets).

### 📄 `.env.dev`
Configuration pour l'environnement de développement.  
**NE JAMAIS COMMITTER** - Contient des secrets de développement.

### 📄 `.env.prod`
Configuration pour l'environnement de production.  
**NE JAMAIS COMMITTER** - Contient des secrets de production.

---

## 🚀 Démarrage Rapide

### Développement

```bash
# 1. Copier le template
cp .env.example .env.dev

# 2. Éditer et remplir les valeurs
nano .env.dev

# 3. Lancer avec Docker Compose
docker-compose -f docker-compose-dev.yml --env-file .env.dev up
```

### Production

```bash
# 1. Copier le template
cp .env.example .env.prod

# 2. Éditer et remplir les valeurs de production (utiliser des valeurs fortes!)
nano .env.prod

# 3. Lancer avec Docker Compose
docker-compose --env-file .env.prod up -d
```

### Important

Le projet utilise à la fois `env_file:` et l'interpolation `${VAR}` dans les fichiers Compose. Pour cette raison, il faut lancer Compose avec `--env-file` afin que les variables utilisées dans le YAML lui-même soient correctement résolues.

---

## 🔐 Bonnes Pratiques de Sécurité

1. **Ne jamais committer les fichiers `.env.dev` ou `.env.prod`**
2. **Utiliser des mots de passe forts** (minimum 16 caractères, aléatoires)
3. **Rotation régulière des secrets** en production
4. **Utiliser un gestionnaire de secrets** (Vault, AWS Secrets Manager, etc.) en production
5. **Restreindre l'accès** aux fichiers `.env` (permissions 600)
6. **Différencier les secrets** dev/staging/prod
7. **Documenter les changements** de configuration

---

## 🛠️ Génération de Secrets Forts

```bash
# Générer un secret aléatoire de 32 caractères
openssl rand -hex 32

# Générer un mot de passe fort
openssl rand -base64 24

# Générer un UUID
uuidgen
```

---

## ⚠️ Résolution de Problèmes

### Erreur: "KEYCLOAK_CLIENT_SECRET must be set in environment variables"
**Solution**: Vérifiez que toutes les variables requises sont définies dans votre fichier `.env`

### Erreur de connexion à Keycloak
**Solution**: Vérifiez les URLs `KEYCLOAK_SERVER_URL` et `KEYCLOAK_INTERNAL_SERVER_URL`

### Erreur de connexion MongoDB/PostgreSQL
**Solution**: Vérifiez que les conteneurs de base de données sont démarrés et accessibles

---

## 📞 Support

Pour toute question ou problème de configuration, contactez:
- **Email**: benjamin.sacristan@chu-bordeaux.fr
- **Documentation**: Voir README.md

---

**Dernière mise à jour**: Février 2026
