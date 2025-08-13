# app.py — Streamlit 오프보딩 앱 (A안: 커스텀 인증, 이전 버전)
from __future__ import annotations

import os
import datetime as dt
from typing import List, Optional

import streamlit as st
from sqlalchemy.orm import Session

from db import (
    init_db,
    SessionLocal,
    User,
    OffboardingCase,
    Role,
    PlanOption,
    CaseStatus,
)
from auth import is_logged_in, login_widget, logout_widget, current_user
from gdrive import upload_bytes


# ─────────────────────────────────────────────────────────────
# 초기화
# ─────────────────────────────────────────────────────────────
init_db()  # 테이블 없으면 생성 (기존 테이블 변경은 X → Alembic 권장)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:8501")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")


# ─────────────────────────────────────────────────────────────
# 텔레그램 알림 헬퍼
# ─────────────────────────────────────────────────────────────
def build_case_link(case_id: int) -> str:
    # Streamlit에 쿼리 파라미터로 case_id 전달
    return f"{PUBLIC_APP_URL}?case_id={case_id}"

def notify_user(user: Optional[User], msg: str, case_id: int) -> None:
    link = build_case_link(case_id)
    if not user:
        st.info(f"수신자 없음 · 링크: {link}")
        return

    if BOT_TOKEN and user.telegram_chat_id:
        try:
            from telegram import Bot  # python-telegram-bot v20 계열
            Bot(BOT_TOKEN).send_message(chat_id=user.telegram_chat_id, text=f"{msg}\n{link}")
            st.success(f"텔레그램 전송: {user.name}")
            return
        except Exception as e:
            st.warning(f"텔레그램 전송 실패({user.name}): {e}")

    # 토큰이 없거나 미연결이면 링크만 안내
    st.info(f"{user.name}에게 알림 필요 · 링크: {link}")


# ─────────────────────────────────────────────────────────────
# 공통 쿼리/유틸
# ─────────────────────────────────────────────────────────────
def list_users_by_role(db: Session, role: Role) -> List[User]:
    return db.query(User).filter(User.role == role).order_by(User.name.asc()).all()

def find_leaver_user(db: Session, case: OffboardingCase) -> Optional[User]:
    # 이름이 정확히 일치하면 매칭(데모용). 운영에선 이메일 컬럼을 케이스에 추가 권장.
    return db.query(User).filter(User.role == Role.leaver, User.name == case.leaver_name).first()

def sync_case_status(case: OffboardingCase) -> None:
    # 승인/상태 자동 전이
    if case.status in {CaseStatus.submitted, CaseStatus.hr_finance_review}:
        if case.hr_approved and case.finance_approved:
            case.status = CaseStatus.docs_requested
    if case.status in {CaseStatus.docs_requested, CaseStatus.docs_submitted}:
        if case.resignation_doc_url and case.handover_doc_url and case.leaver_final_approved:
            case.status = CaseStatus.docs_submitted
    # 최종 완료 조건
    if (
        case.hr_approved
        and case.finance_approved
        and case.leaver_final_approved
        and case.manager_final_approved
    ):
        case.status = CaseStatus.completed


# ─────────────────────────────────────────────────────────────
# 페이지: 팀장(Manager)
# ─────────────────────────────────────────────────────────────
def page_manager(db: Session, me: User) -> None:
    st.header("팀장 대시보드")

    with st.expander("➕ 오프보딩 케이스 생성", expanded=True):
        with st.form("create_case"):
            leaver_name = st.text_input("퇴사자 이름", "")
            leaver_dept = st.text_input("퇴사자 소속(부서)", "")
            desired_date = st.date_input("퇴사 희망일자", value=dt.date.today())
            plan = st.radio(
                "퇴사 이후 내부 팀 계획",
                options=list(PlanOption),
                format_func=lambda x: "신규인력채용" if x == PlanOption.new_hire else "팀내부해결",
                horizontal=True,
            )
            # HR/회계 담당자 배정
            hrs = list_users_by_role(db, Role.hr)
            fins = list_users_by_role(db, Role.finance)
            hr_sel = st.selectbox("HR 담당자", options=hrs, format_func=lambda u: f"{u.name} ({u.email})")
            fin_sel = st.selectbox("회계 담당자", options=fins, format_func=lambda u: f"{u.name} ({u.email})")
            create_btn = st.form_submit_button("케이스 생성")

        if create_btn:
            if not leaver_name:
                st.error("퇴사자 이름은 필수입니다.")
            else:
                case = OffboardingCase(
                    leaver_name=leaver_name,
                    leaver_department=leaver_dept or None,
                    desired_leave_date=desired_date,
                    plan_option=plan,
                    manager_id=me.id,
                    hr_owner_id=hr_sel.id if hr_sel else None,
                    finance_owner_id=fin_sel.id if fin_sel else None,
                    status=CaseStatus.created,
                )
                db.add(case)
                db.commit()
                st.success(f"케이스 생성 완료 (ID: {case.id})")

    my_cases = (
        db.query(OffboardingCase)
        .filter(OffboardingCase.manager_id == me.id)
        .order_by(OffboardingCase.created_at.desc())
        .all()
    )
    st.subheader("내 케이스")
    for c in my_cases:
        with st.expander(f"[#{c.id}] {c.leaver_name} · {c.status.value}", expanded=False):
            st.write(f"부서: {c.leaver_department or '-'} / 희망일: {c.desired_leave_date or '-'}")
            st.write(f"계획: {('신규인력채용' if c.plan_option == PlanOption.new_hire else '팀내부해결') if c.plan_option else '-'}")
            st.write(f"HR: {c.hr_owner.name if c.hr_owner else '-'} / 회계: {c.finance_owner.name if c.finance_owner else '-'}")
            st.write(f"HR 승인: {c.hr_approved} / 회계 승인: {c.finance_approved}")
            st.write(f"퇴사자 승인: {c.leaver_final_approved} / 팀장 최종 승인: {c.manager_final_approved}")
            if c.resignation_doc_url:
                st.write(f"사직서: {c.resignation_doc_url}")
            if c.handover_doc_url:
                st.write(f"인수인계서: {c.handover_doc_url}")

            cols = st.columns(3)
            with cols[0]:
                if st.button("HR/회계에 제출", key=f"submit_{c.id}", disabled=c.status not in {CaseStatus.created, CaseStatus.rejected}):
                    c.status = CaseStatus.submitted
                    db.commit()
                    # 알림
                    if c.hr_owner:
                        notify_user(c.hr_owner, f"[오프보딩 제출] 케이스 #{c.id} HR 검토 요청", c.id)
                    if c.finance_owner:
                        notify_user(c.finance_owner, f"[오프보딩 제출] 케이스 #{c.id} 회계 검토 요청", c.id)
                    st.rerun()
            with cols[1]:
                approve_now = st.button("팀장 최종 승인", key=f"mgr_ok_{c.id}", disabled=c.status != CaseStatus.docs_submitted or c.manager_final_approved)
                if approve_now:
                    c.manager_final_approved = True
                    sync_case_status(c)
                    db.commit()
                    # 완료 시 알림
                    if c.status == CaseStatus.completed:
                        if c.hr_owner:
                            notify_user(c.hr_owner, f"[완료] 케이스 #{c.id} 최종 완료", c.id)
                        leaver = find_leaver_user(db, c)
                        if leaver:
                            notify_user(leaver, f"[완료] 케이스 #{c.id} 최종 완료", c.id)
                    st.rerun()
            with cols[2]:
                if st.button("반려/보류", key=f"reject_{c.id}", disabled=c.status == CaseStatus.completed):
                    c.status = CaseStatus.rejected
                    db.commit()
                    st.rerun()


# ─────────────────────────────────────────────────────────────
# 페이지: HR
# ─────────────────────────────────────────────────────────────
def page_hr(db: Session, me: User) -> None:
    st.header("HR 대시보드")

    cases = (
        db.query(OffboardingCase)
        .filter(
            (OffboardingCase.hr_owner_id == me.id)
            | (OffboardingCase.hr_owner_id.is_(None))
        )
        .order_by(OffboardingCase.created_at.desc())
        .all()
    )

    for c in cases:
        with st.expander(f"[#{c.id}] {c.leaver_name} · {c.status.value}", expanded=False):
            st.write(f"팀장: {c.manager.name if c.manager else '-'} / 회계: {c.finance_owner.name if c.finance_owner else '-'}")
            st.write(f"희망일자: {c.desired_leave_date or '-'}")
            # 입력/승인
            rem = st.number_input("남은 연차", min_value=0.0, step=0.5, value=float(c.hr_remaining_leave or 0), key=f"hr_rem_{c.id}")
            approve = st.checkbox("HR 승인", value=bool(c.hr_approved), key=f"hr_ok_{c.id}")

            if st.button("저장", key=f"hr_save_{c.id}"):
                c.hr_remaining_leave = rem
                c.hr_approved = approve
                # 상태 동기화 및 알림
                prev_status = c.status
                sync_case_status(c)
                db.commit()

                # 두 승인(HR/회계) 완료 → 퇴사자/팀장에 문서 요청
                if prev_status in {CaseStatus.submitted, CaseStatus.hr_finance_review} and c.status == CaseStatus.docs_requested:
                    if c.manager:
                        notify_user(c.manager, f"[문서요청] 케이스 #{c.id} 사직서/인수인계 업로드 요청", c.id)
                    leaver = find_leaver_user(db, c)
                    if leaver:
                        notify_user(leaver, f"[문서요청] 케이스 #{c.id} 사직서/인수인계 업로드 요청", c.id)

                st.success("저장되었습니다.")
                st.rerun()


# ─────────────────────────────────────────────────────────────
# 페이지: 회계(Finance)
# ─────────────────────────────────────────────────────────────
def page_finance(db: Session, me: User) -> None:
    st.header("회계 대시보드")

    cases = (
        db.query(OffboardingCase)
        .filter(
            (OffboardingCase.finance_owner_id == me.id)
            | (OffboardingCase.finance_owner_id.is_(None))
        )
        .order_by(OffboardingCase.created_at.desc())
        .all()
    )

    for c in cases:
        with st.expander(f"[#{c.id}] {c.leaver_name} · {c.status.value}", expanded=False):
            st.write(f"팀장: {c.manager.name if c.manager else '-'} / HR: {c.hr_owner.name if c.hr_owner else '-'}")
            # 입력/승인
            sev = st.number_input("퇴직금 정산액", min_value=0.0, step=100000.0, value=float(c.finance_severance or 0), key=f"fin_sev_{c.id}")
            approve = st.checkbox("회계 승인", value=bool(c.finance_approved), key=f"fin_ok_{c.id}")

            if st.button("저장", key=f"fin_save_{c.id}"):
                c.finance_severance = sev
                c.finance_approved = approve
                prev_status = c.status
                sync_case_status(c)
                db.commit()

                # 두 승인 완료 → 문서요청 알림
                if prev_status in {CaseStatus.submitted, CaseStatus.hr_finance_review} and c.status == CaseStatus.docs_requested:
                    if c.manager:
                        notify_user(c.manager, f"[문서요청] 케이스 #{c.id} 사직서/인수인계 업로드 요청", c.id)
                    leaver = find_leaver_user(db, c)
                    if leaver:
                        notify_user(leaver, f"[문서요청] 케이스 #{c.id} 사직서/인수인계 업로드 요청", c.id)

                st.success("저장되었습니다.")
                st.rerun()


# ─────────────────────────────────────────────────────────────
# 페이지: 퇴사자(Leaver)
# ─────────────────────────────────────────────────────────────
def page_leaver(db: Session, me: User) -> None:
    st.header("퇴사자 화면")

    # 데모: 내 이름과 동일한 케이스만 필터(운영에선 OffboardingCase에 leaver_email 컬럼을 추가 권장)
    cases = (
        db.query(OffboardingCase)
        .filter(OffboardingCase.leaver_name == me.name)
        .order_by(OffboardingCase.created_at.desc())
        .all()
    )
    if not cases:
        st.info("내 이름으로 생성된 케이스가 없습니다. (운영에서는 이메일 매핑을 권장합니다.)")
        return

    for c in cases:
        with st.expander(f"[#{c.id}] {c.leaver_name} · {c.status.value}", expanded=True):
            st.write(f"남은 연차: {c.hr_remaining_leave if c.hr_remaining_leave is not None else '-'}")
            st.write(f"퇴직금: {c.finance_severance if c.finance_severance is not None else '-'}")

            # 사직서/인수인계 업로드
            resign = st.file_uploader("사직서(PDF)", type=["pdf"], key=f"resign_{c.id}")
            handover = st.file_uploader("인수인계서(PDF)", type=["pdf"], key=f"handover_{c.id}")

            cols = st.columns(2)
            with cols[0]:
                if resign:
                    if st.button("사직서 업로드", key=f"resign_btn_{c.id}"):
                        rbytes = resign.read()
                        meta = upload_bytes(rbytes, f"resignation_case_{c.id}.pdf", resign.type or "application/pdf", GDRIVE_FOLDER_ID)
                        c.resignation_doc_url = meta.get("webViewLink") or meta.get("webContentLink")
                        db.commit()
                        st.success("사직서 업로드 완료")
                        st.rerun()
            with cols[1]:
                if handover:
                    if st.button("인수인계서 업로드", key=f"handover_btn_{c.id}"):
                        hbytes = handover.read()
                        meta = upload_bytes(hbytes, f"handover_case_{c.id}.pdf", handover.type or "application/pdf", GDRIVE_FOLDER_ID)
                        c.handover_doc_url = meta.get("webViewLink") or meta.get("webContentLink")
                        db.commit()
                        st.success("인수인계서 업로드 완료")
                        st.rerun()

            if c.resignation_doc_url:
                st.write(f"사직서 링크: {c.resignation_doc_url}")
            if c.handover_doc_url:
                st.write(f"인수인계서 링크: {c.handover_doc_url}")

            approve = st.checkbox("내용 확인 및 승인", value=bool(c.leaver_final_approved), key=f"leaver_ok_{c.id}")
            if st.button("승인 저장", key=f"leaver_save_{c.id}"):
                c.leaver_final_approved = approve
                prev_status = c.status
                sync_case_status(c)
                db.commit()
                # 문서 업로드 + 승인이 완료되면 팀장에게 알림
                if prev_status in {CaseStatus.docs_requested} and c.status == CaseStatus.docs_submitted and c.manager:
                    notify_user(c.manager, f"[검토요청] 케이스 #{c.id} 서류 제출 완료", c.id)
                st.success("저장되었습니다.")
                st.rerun()


# ─────────────────────────────────────────────────────────────
# 라우터
# ─────────────────────────────────────────────────────────────
def router() -> None:
    # 미로그인: 로그인 폼 표시
    if not is_logged_in():
        login_widget()
        return

    # 로그인 유저
    with SessionLocal() as db:
        me = current_user(db)
        if not me:
            # 세션 꼬임 대비
            from auth import do_logout
            do_logout()
            return

        # 사이드바에 로그아웃 버튼 노출
        logout_widget()

        # 쿼리 파라미터의 case_id가 있으면 안내 표시 (최신 streamlit에 존재)
        q_case_id = st.query_params.get("case_id", None)
        if q_case_id:
            st.info(f"열람 대상 케이스 ID: {q_case_id}")

        # 역할별 페이지 라우팅
        if me.role == Role.manager:
            page_manager(db, me)
        elif me.role == Role.hr:
            page_hr(db, me)
        elif me.role == Role.finance:
            page_finance(db, me)
        elif me.role == Role.leaver:
            page_leaver(db, me)
        else:
            st.write("권한이 없습니다. 관리자에게 문의하세요.")


# ─────────────────────────────────────────────────────────────
# 엔트리포인트
# ─────────────────────────────────────────────────────────────
def main() -> None:
    st.set_page_config(page_title="Offboarding", page_icon="🧾", layout="wide")
    router()

if __name__ == "__main__":
    main()

