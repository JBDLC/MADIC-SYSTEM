# Déploiement MADIC SYSTEM sur Render

## Option 1 : Blueprint (recommandé)

1. Poussez le code sur GitHub
2. Sur [Render](https://render.com), créez un nouveau **Blueprint**
3. Connectez le dépôt : Render détecte `render.yaml` et crée automatiquement :
   - Une base PostgreSQL (version 18 disponible sur Render)
   - L'application web reliée à la base

La variable `DATABASE_URL` est injectée automatiquement. La base est créée vide ; les tables sont créées au premier lancement de l'app (SQLAlchemy `create_all`).

## Option 2 : Base PostgreSQL existante

Si vous avez déjà une base PostgreSQL (ex. version 18) :

1. Créez un **Web Service** sur Render
2. Dans **Environment** : ajoutez `DATABASE_URL` avec l’URL de connexion (depuis le dashboard de votre base)
3. `SECRET_KEY` : générez une clé (ex. `python -c "import secrets; print(secrets.token_hex(24))"`)
4. **Build** : `pip install -r requirements.txt`
5. **Start** : `gunicorn app:app --bind 0.0.0.0:$PORT`

## Variables d'environnement

| Variable      | Description                                      |
|---------------|---------------------------------------------------|
| `DATABASE_URL`| URL de connexion PostgreSQL (fournie par Render) |
| `SECRET_KEY`  | Clé secrète Flask (générée automatiquement)      |
| `PORT`        | Port d’écoute (fourni par Render)                |

## Note

- En local : SQLite (`madic_data.db`)
- Sur Render : PostgreSQL (si `DATABASE_URL` est définie)
