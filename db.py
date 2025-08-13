# db.py (full replacement)
from __future__ import annotations

import os
import pathlib
import enum as pyenum
from typing import Optional

from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Date,
    Boolean,
    Float,
    ForeignKey,
    DateTime,
    Text,
    Enum as SAEnum,
    func,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ─────────────────────────────────────────────────────────────
# .env 로드 (프로젝트 루트의 .env를 확실히 읽도록 경로 지정)
# ─────────────────────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ─────────────────────────────────────────────────────────────
# DB URL 구성
# 1) DATABASE_URL (예: postgresql+psycopg://... )
# 2) 없으면 PG_HOST/PG_USER/PG_PASSWORD/PG_PORT/PG_DB 로 안전 조합
# 3) 그래도 없으면 개발용 SQLite로 폴백
# ─────────────────────────────────────────────────────────────
_database_url: Optional[str] = os.getenv("DATABASE_URL")

if not _database_url:
    pg_host = os.getenv("PG_HOST")
    pg_user = os.getenv("PG_USER")
    pg_password = os.getenv("PG_PASSWORD")
    pg_port = os.getenv("PG_PORT")
    pg_db = os.getenv("PG_DB")

    if all([pg_host, pg_user, pg_password, pg_port, pg_db]):
        # URL.create 를 쓰면 비밀번호 특수문자 인코딩을 신경쓸 필요가 없습니다.
        url_obj = URL.create(
            "postgresql+psycopg",
            username=pg_user,
            password=pg_password,
            host=pg_host,
            port=int(pg_port),
            database=pg_db,
            query={"sslmode": "require"},
        )
        _database_url = str(url_obj)

if not _database_url:
    # 개발용 SQLite 폴백 (원치 않으면 이 블록 제거)
    sqlite_path = BASE_DIR / "data" / "app.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    _database_url = f"sqlite:///{sqlite_path}"

# ─────────────────────────────────────────────────────────────
# SQLAlchemy Engine / Session
#  - Supabase PgBouncer(6543, 트랜잭션 모드) 호환을 위해
#    psycopg의 서버사이드 prepared statements 를 비활성화합니다.
# ─────────────────────────────────────────────────────────────
is_sqlite = _database_url.startswith("sqlite")
connect_args = {}

if is_sqlite:
    # SQLite는 멀티스레드 접근 시 이 옵션이 필요할 수 있습니다.
    connect_args = {"check_same_thread": False}
else:
    # ★ 핵심: PgBouncer 트랜잭션 모드에서 prepared statements 사용 금지
    # psycopg 3: prepare_threshold=None → 완전 비활성화
    connect_args = {"prepare_threshold": None}

engine = create_engine(
    _database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()

# ─────────────────────────────────────────────────────────────
# Enum 정의
# ─────────────────────────────────────────────────────────────
class Role(pyenum.Enum):
    admin = "admin"
    manager = "manager"
    hr = "hr"
    finance = "finance"
    leaver = "leaver"


class PlanOption(pyenum.Enum):
    new_hire = "new_hire"            # 신규인력채용
    internal_fill = "internal_fill"  # 팀내부해결


class CaseStatus(pyenum.Enum):
    created = "created"                       # 생성됨 (팀장 작성 중)
    submitted = "submitted"                   # HR/회계에 제출됨
    hr_finance_review = "hr_finance_review"   # HR/회계 검토 중
    docs_requested = "docs_requested"         # 퇴사자 문서 요청됨
    docs_submitted = "docs_submitted"         # 퇴사자 문서 업로드됨
    manager_review = "manager_review"         # 팀장 최종 검토
    completed = "completed"                   # 최종 완료
    rejected = "rejected"                     # 반려/보류

# ─────────────────────────────────────────────────────────────
# 모델 정의
# ─────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    # bcrypt 해시 저장 (예: $2b$12$... )
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(Role, name="role_enum"), nullable=False, index=True)

    telegram_chat_id = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 관계(옵션)
    managed_cases = relationship(
        "OffboardingCase",
        back_populates="manager",
        foreign_keys="OffboardingCase.manager_id",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role.value}>"


class OffboardingCase(Base):
    __tablename__ = "offboarding_cases"

    id = Column(Integer, primary_key=True)

    # 기본 정보
    leaver_name = Column(String(255), nullable=False)
    leaver_department = Column(String(255), nullable=True)
    desired_leave_date = Column(Date, nullable=True)

    plan_option = Column(SAEnum(PlanOption, name="plan_option_enum"), nullable=True)

    # 담당자
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    hr_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    finance_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    manager = relationship("User", foreign_keys=[manager_id], back_populates="managed_cases")
    hr_owner = relationship("User", foreign_keys=[hr_owner_id])
    finance_owner = relationship("User", foreign_keys=[finance_owner_id])

    # HR/회계 입력값
    hr_remaining_leave = Column(Float, nullable=True)   # 남은 연차
    finance_severance = Column(Float, nullable=True)    # 퇴직금 정산액

    # 승인 여부
    hr_approved = Column(Boolean, default=False, nullable=False)
    finance_approved = Column(Boolean, default=False, nullable=False)
    manager_final_approved = Column(Boolean, default=False, nullable=False)
    leaver_final_approved = Column(Boolean, default=False, nullable=False)

    # 문서 링크 (Google Drive 등)
    resignation_doc_url = Column(Text, nullable=True)
    handover_doc_url = Column(Text, nullable=True)

    # 상태
    status = Column(SAEnum(CaseStatus, name="case_status_enum"), default=CaseStatus.created, nullable=False, index=True)

    # 메모/코멘트
    note = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<OffboardingCase id={self.id} leaver={self.leaver_name} status={self.status.value}>"

# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────
def init_db() -> None:
    """
    테이블이 없으면 생성합니다. (모든 모델 선언 이후 호출)
    기존 테이블의 컬럼 추가/변경은 수행하지 않으므로, 스키마 변경 시 Alembic을 권장합니다.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    세션 제네레이터. with 문 없이 사용할 경우 try/finally로 close 필요.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

