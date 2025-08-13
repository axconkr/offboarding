

## Google Drive Storage (Service Account)

1) **Google Cloud → APIs & Services**에서 Drive API 사용 설정
2) **Service Account** 생성 → 키(JSON) 생성
3) Google Drive에서 업로드 대상 **폴더를 만들고**, 서비스 계정 이메일(예: `svc-name@project.iam.gserviceaccount.com`)에 **편집 권한** 공유
4) `.env` 설정
```
GDRIVE_FOLDER_ID=your_folder_id_here
# 방법 A: 파일 경로 사용
GOOGLE_SERVICE_ACCOUNT_FILE=/absolute/path/to/service-account.json
# 방법 B: JSON 문자열 직접 삽입
# GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account", ...}
GDRIVE_PUBLIC_LINKS=true   # 업로드 후 링크 공개(선택)
```
5) 앱 실행 후, 퇴사자 화면에서 PDF 업로드 → Google Drive에 저장되고, 링크가 DB에 기록됩니다.
