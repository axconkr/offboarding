# gdrive_oauth_bootstrap.py
import os, json, pathlib
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

BASE = pathlib.Path(__file__).parent
client_secrets = BASE / "client_secret.json"  # 방금 받은 파일명
flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
creds = flow.run_local_server(port=0)
(BASE / "token.json").write_text(creds.to_json())
svc = build("drive", "v3", credentials=creds)
print("OAuth OK. email bound.")
