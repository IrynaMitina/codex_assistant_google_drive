# Git Drive REST API Base

This project is a small Google Drive-like REST backend built with FastAPI. It supports JWT login, folder creation, file upload/download, soft deletion, and resource sharing through `viewer` and `editor` permissions.

For a fuller new-engineer walkthrough, see [docs/reverse-engineering/overview.md](docs/reverse-engineering/overview.md).

## Quick Start

Create a local `.env.dev`:

```bash
cat > .env.dev <<'EOF'
APP_ENV=dev
DEBUG=true
LOG_LEVEL=INFO
DATABASE_URL_TEMPLATE=sqlite+aiosqlite:///./drive.db
STORAGE_DIR=./storage
JWT_SECRET_KEY=dev-secret-change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
EOF
```

Install dependencies, migrate the database, seed demo users, and launch the API:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

Swagger UI is available at `http://127.0.0.1:8000/docs`.

## Run Tests

```bash
python -m pytest
```

## Typical Local Scenario With curl

Login as Alice:

```bash
ALICE_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=alice123" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Login as Bob:

```bash
BOB_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=bob@example.com&password=bob123" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Create a folder as Alice:

```bash
FOLDER_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/drive/folders \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"docs","parent_id":null}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "$FOLDER_ID"
```

Upload a file into the created folder:

```bash
printf "hello shared drive\n" > /tmp/a.txt
FILE_ID=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/drive/folders/$FOLDER_ID/files" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -F "upload=@/tmp/a.txt;type=text/plain" \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "$FILE_ID"
```

List the folder contents:

```bash
curl -s "http://127.0.0.1:8000/api/v1/drive/folders/$FOLDER_ID/contents" \
  -H "Authorization: Bearer $ALICE_TOKEN"
```

Verify Bob cannot download the file yet:

```bash
curl -i "http://127.0.0.1:8000/api/v1/drive/files/$FILE_ID/download" \
  -H "Authorization: Bearer $BOB_TOKEN"
```

Share the file with Bob as a viewer:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/drive/file/$FILE_ID/share" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":2,"role":"viewer"}'
```

Download the file as Bob:

```bash
curl -s "http://127.0.0.1:8000/api/v1/drive/files/$FILE_ID/download" \
  -H "Authorization: Bearer $BOB_TOKEN"
```

Delete the file as Alice:

```bash
curl -i -X DELETE "http://127.0.0.1:8000/api/v1/drive/files/$FILE_ID" \
  -H "Authorization: Bearer $ALICE_TOKEN"
```
