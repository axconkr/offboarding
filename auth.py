# auth.py  — A안: 커스텀 로그인/로그아웃 (SessionState 기반)
from __future__ import annotations

import streamlit as st
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select
import bcrypt

from db import SessionLocal, User  # SQLAlchemy 모델/세션


# ─────────────────────────────────────────────────────────────
# SessionState 키 정의
# ─────────────────────────────────────────────────────────────
AUTH_KEYS = [
    "auth_is_authenticated",
    "auth_user_id",
    "auth_email",
    "auth_name",
    "auth_role",
]


# ─────────────────────────────────────────────────────────────
# 헬퍼: 비밀번호 검증 (bcrypt)
# ─────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# 로그인/로그아웃 상태 관리
# ─────────────────────────────────────────────────────────────
def set_logged_in(user: User) -> None:
    """로그인 성공 시 세션에 사용자 정보를 기록"""
    st.session_state["auth_is_authenticated"] = True
    st.session_state["auth_user_id"] = user.id
    st.session_state["auth_email"] = user.email
    st.session_state["auth_name"] = user.name
    # SQLAlchemy Enum(Role) → 문자열
    st.session_state["auth_role"] = getattr(user.role, "value", str(user.role))


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_is_authenticated"))


def do_logout() -> None:
    """세션에서 인증 관련 키만 제거하고 즉시 새로고침"""
    for k in AUTH_KEYS:
        if k in st.session_state:
            st.session_state.pop(k, None)
    # Streamlit 1.27+ 는 st.rerun 사용 가능. 호환을 위해 experimental 유지.
    st.rerun()


def logout_widget() -> None:
    """사이드바에 로그아웃 버튼 표시"""
    with st.sidebar:
        st.markdown("---")
        user_name = st.session_state.get("auth_name", "")
        user_email = st.session_state.get("auth_email", "")
        if user_name or user_email:
            st.caption(f"로그인: {user_name} ({user_email})")
        if st.button("🔒 로그아웃", use_container_width=True):
            do_logout()


def current_user(db: Optional[Session] = None) -> Optional[User]:
    """세션의 사용자 id로 DB에서 User 객체를 조회"""
    uid = st.session_state.get("auth_user_id")
    if not uid:
        return None
    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True
    try:
        return db.get(User, uid)
    finally:
        if close_after:
            db.close()


# ─────────────────────────────────────────────────────────────
# (호환용) 전체 사용자 자격증명 맵 반환
#  - 기존 코드가 get_credentials_map(db)를 호출하는 경우를 대비
# ─────────────────────────────────────────────────────────────
def get_credentials_map(db: Session) -> Dict[str, Dict[str, Any]]:
    creds: Dict[str, Dict[str, Any]] = {}
    for u in db.execute(select(User)).scalars():
        creds[u.email] = {
            "name": u.name,
            "password_hash": u.password_hash,
            "role": getattr(u.role, "value", str(u.role)),
        }
    return creds


# ─────────────────────────────────────────────────────────────
# 로그인 위젯 (이메일/비밀번호) — 성공 시 set_logged_in + rerun
# ─────────────────────────────────────────────────────────────
def login_widget() -> None:
    st.title("로그인")

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("이메일", key="login_email")
        password = st.text_input("비밀번호", type="password", key="login_password")
        submitted = st.form_submit_button("로그인")

    if submitted:
        # DB에서 사용자 조회
        with SessionLocal() as db:
            user: Optional[User] = db.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

        if not user:
            st.error("등록되지 않은 이메일입니다.")
            return

        if not verify_password(password, user.password_hash):
            st.error("비밀번호가 올바르지 않습니다.")
            return

        # 로그인 성공
        set_logged_in(user)
        st.success(f"{user.name} 님 환영합니다!")
        st.rerun()

