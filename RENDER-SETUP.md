# Configuration Render — éviter Python 3.14

Si tu as encore l’erreur SQLAlchemy avec Python 3.14, utilise le **Dockerfile** :

## Option A : Build via Docker (recommandé)

1. **Dashboard Render** → ton Web Service → **Settings**
2. **Build & Deploy** :
   - **Environment** : passe de `Python` à **Docker**
   - Sauvegarde
3. Render va détecter le `Dockerfile` et construire avec Python 3.11.

Build command et Start command ne sont plus nécessaires, le Dockerfile les définit.

## Option B : Garder Python mais forcer 3.11

1. **Environment** → ajoute :
   - `PYTHON_VERSION` = `3.11.11`
2. **Settings** → **Build** → coche **Clear build cache & deploy**
3. Redéploie.

Si ça ne suffit pas, utilise l’option A (Docker).
