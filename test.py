# venv 활성화 후 python에서 실행
import os, json, io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

# 자격 증명 로드 (파일 or JSON)
if os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"), scopes=SCOPES)
else:
    info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

svc = build("drive", "v3", credentials=creds)
content = b"hello from service account"
media = MediaIoBaseUpload(io.BytesIO(content), mimetype="text/plain", resumable=True)
meta = {"name": "test.txt"}
if FOLDER_ID:
    meta["parents"] = [FOLDER_ID]

f = svc.files().create(
    body=meta, media_body=media,
    fields="id, name, webViewLink, webContentLink",
    supportsAllDrives=True
).execute()
print(f)

