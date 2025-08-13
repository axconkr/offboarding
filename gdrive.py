# gdrive.py (요지)
import os, io, json
from typing import Optional, Dict
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

def _load_credentials():
    # 1) 서비스 계정 우선
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if sa_json or sa_file:
        try:
            if sa_json:
                info = json.loads(sa_json)
                return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
        except Exception:
            pass
    # 2) OAuth 토큰 폴백
    token_path = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token.json")
    if os.path.exists(token_path):
        return Credentials.from_authorized_user_file(token_path, SCOPES)
    raise RuntimeError("No Drive credentials. Set service account env or provide token.json")

def _drive_service():
    return build("drive", "v3", credentials=_load_credentials(), cache_discovery=False)

def upload_bytes(content: bytes, filename: str, mime_type: str, folder_id: Optional[str] = None) -> Dict[str, str]:
    svc = _drive_service()
    metadata = {"name": filename}
    if folder_id: metadata["parents"] = [folder_id]
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=True)
    file = svc.files().create(
        body=metadata, media_body=media,
        fields="id, name, mimeType, webViewLink, webContentLink, parents",
        supportsAllDrives=True
    ).execute()
    return file

