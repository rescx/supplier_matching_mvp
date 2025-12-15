from datetime import datetime
from typing import List, Optional

import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, or_

load_dotenv()
from .database import init_db, get_session
from .models import (
    PriceItem,
    PriceSupplierGroup,
    Supplier,
    SupplierMapping,
    SellerIssue,
    SellerToken,
    SupplierMappingStatus,
    ModerationEvent,
    ModerationDecision,
)
from .schemas import (
    AdminLoginRequest,
    AnalyticsMappingOut,
    IssueCreate,
    IssueOut,
    MappingModerationResponse,
    MappingRequest,
    ModerationEventOut,
    PriceItemImport,
    PriceSupplierGroupOut,
    RejectRequest,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from .utils import normalize_inn
from .auth import ADMIN_USERNAME, ADMIN_PASSWORD, create_admin_session, get_admin_user


app = FastAPI(title="Supplier Mapping Service")

origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://localhost:3000",
)
origins = [o.strip() for o in origins_env.split(",") if o.strip()]
origin_regex = ".*" if "*" in origins else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


REJECTION_REASONS = {
    "WRONG_INN": "ИНН указан неверно",
    "WRONG_SUPPLIER": "Выбран неверный поставщик",
    "NEED_MORE_INFO": "Недостаточно данных, уточните информацию",
    "SUPPLIER_NOT_FOUND": "Поставщик отсутствует в справочнике",
    "DUPLICATE_REQUEST": "Дубликат заявки",
}


# --------- Helpers ---------
def log_moderation_event(
    session: Session,
    mapping: SupplierMapping,
    decision: ModerationDecision,
    admin_user: str,
    reject_reason_code: Optional[str] = None,
    reject_comment_internal: Optional[str] = None,
) -> ModerationEvent:
    reason_label = REJECTION_REASONS.get(reject_reason_code) if reject_reason_code else None
    event = ModerationEvent(
        owner_id=mapping.owner_id,
        packet_id=mapping.packet_id,
        supplier_group_id=mapping.group_id,
        mapping_id=mapping.id,
        decision=decision,
        decided_at=datetime.utcnow(),
        decided_by=admin_user,
        reject_reason_code=reject_reason_code,
        reject_reason_label=reason_label,
        reject_comment_internal=reject_comment_internal,
    )
    session.add(event)
    return event


def latest_mapping_for_group(session: Session, group_id: int) -> Optional[SupplierMapping]:
    return session.exec(
        select(SupplierMapping)
        .where(SupplierMapping.group_id == group_id)
        .order_by(SupplierMapping.created_at.desc())
    ).first()


def last_reject_event_for_group(session: Session, group_id: int) -> Optional[ModerationEvent]:
    return session.exec(
        select(ModerationEvent)
        .where(
            ModerationEvent.supplier_group_id == group_id,
            ModerationEvent.decision == ModerationDecision.REJECTED,
        )
        .order_by(ModerationEvent.decided_at.desc())
    ).first()


def resolve_group_status(session: Session, group: PriceSupplierGroup) -> PriceSupplierGroupOut:
    mapping = latest_mapping_for_group(session, group.id)
    status_value = "UNMAPPED"
    canonical_name = None
    canonical_id = None
    latest_status = None
    latest_decision_at = None
    reject_reason_label = None
    if mapping:
        # mapping.status can be Enum or string
        status_value = mapping.status.value if hasattr(mapping.status, "value") else mapping.status
        canonical_name = mapping.canonical_supplier.supplier if mapping.canonical_supplier else None
        canonical_id = mapping.canonical_supplier_id
        latest_status = status_value
        latest_decision_at = mapping.updated_at or mapping.created_at
        if status_value == SupplierMappingStatus.REJECTED.value:
            ev = last_reject_event_for_group(session, group.id)
            if ev:
                reject_reason_label = ev.reject_reason_label
                latest_decision_at = ev.decided_at
    return PriceSupplierGroupOut(
        id=group.id,
        owner_id=group.owner_id,
        packet_id=group.packet_id,
        inn_norm=group.inn_norm,
        inn_invalid=group.inn_invalid,
        std_supplier_raw=group.std_supplier_raw,
        items_count=group.items_count,
        status=status_value,
        canonical_supplier=canonical_name,
        canonical_supplier_id=canonical_id,
        latest_status=latest_status,
        latest_decision_at=latest_decision_at,
        reject_reason_label=reject_reason_label,
    )


def get_seller_context(token: str, session: Session) -> SellerToken:
    token_obj = session.exec(select(SellerToken).where(SellerToken.token == token)).first()
    if not token_obj:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if token_obj.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return token_obj


# --------- Import API ---------
@app.post("/api/import/price_items")
def import_price_items(items: List[PriceItemImport], session: Session = Depends(get_session)):
    now = datetime.utcnow()
    for payload in items:
        inn_norm, inn_invalid = normalize_inn(payload.inn)
        pi = PriceItem(
            owner_id=payload.ownerId,
            packet_id=payload.packetId,
            inn=payload.inn or "",
            inn_norm=inn_norm,
            inn_invalid=inn_invalid,
            std_supplier=payload.std_supplier,
            item_id=payload.itemId,
            created_at=now,
        )
        session.add(pi)

        group = session.exec(
            select(PriceSupplierGroup).where(
                PriceSupplierGroup.owner_id == payload.ownerId,
                PriceSupplierGroup.packet_id == payload.packetId,
                PriceSupplierGroup.inn_norm == inn_norm,
                PriceSupplierGroup.std_supplier_raw == payload.std_supplier,
            )
        ).first()
        if not group:
            group = PriceSupplierGroup(
                owner_id=payload.ownerId,
                packet_id=payload.packetId,
                inn_norm=inn_norm,
                std_supplier_raw=payload.std_supplier,
                items_count=0,
                inn_invalid=inn_invalid,
                created_at=now,
                updated_at=now,
            )
            session.add(group)
        group.items_count += 1
        group.inn_invalid = inn_invalid
        group.updated_at = now
    session.commit()
    return {"imported": len(items)}


# --------- Seller API ---------
@app.get("/api/seller/groups", response_model=List[PriceSupplierGroupOut])
def list_groups(token: str, session: Session = Depends(get_session)):
    seller = get_seller_context(token, session)
    groups = session.exec(
        select(PriceSupplierGroup).where(
            PriceSupplierGroup.owner_id == seller.owner_id,
            PriceSupplierGroup.packet_id == seller.packet_id,
        )
    ).all()
    return [resolve_group_status(session, g) for g in groups]


@app.get("/api/seller/suppliers", response_model=List[SupplierOut])
def search_suppliers(q: str = "", session: Session = Depends(get_session)):
    q_norm = (q or "").strip()
    suppliers = session.exec(select(Supplier).order_by(Supplier.supplier)).all()
    if not q_norm:
        return suppliers
    needle = q_norm.casefold()
    return [
        s
        for s in suppliers
        if needle in (s.supplier or "").casefold() or needle in (s.inn or "").casefold()
    ]


@app.post("/api/seller/mappings")
def create_mapping(request: MappingRequest, session: Session = Depends(get_session)):
    seller = get_seller_context(request.token, session)
    group = session.get(PriceSupplierGroup, request.group_id)
    if not group or group.owner_id != seller.owner_id or group.packet_id != seller.packet_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    supplier = session.get(Supplier, request.canonical_supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

    mapping = SupplierMapping(
        group_id=group.id,
        canonical_supplier_id=supplier.id,
        owner_id=group.owner_id,
        packet_id=group.packet_id,
        status=SupplierMappingStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        std_supplier_raw=group.std_supplier_raw,
        inn_norm=group.inn_norm,
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return {"status": "PENDING", "mapping_id": mapping.id}


@app.post("/api/seller/issues", response_model=IssueOut)
def create_issue(payload: IssueCreate, session: Session = Depends(get_session)):
    seller = get_seller_context(payload.token, session)
    group = session.get(PriceSupplierGroup, payload.group_id)
    if not group or group.owner_id != seller.owner_id or group.packet_id != seller.packet_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    issue = SellerIssue(
        owner_id=seller.owner_id,
        packet_id=seller.packet_id,
        group_id=group.id,
        inn=group.inn_norm,
        inn_norm=group.inn_norm,
        std_supplier=group.std_supplier_raw,
        comment=payload.comment,
        created_at=datetime.utcnow(),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


# --------- Admin Auth ---------
@app.post("/api/admin/login")
def admin_login(payload: AdminLoginRequest, response: Response):
    if payload.username != ADMIN_USERNAME or payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_admin_session(payload.username)
    response.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        samesite="lax",
    )
    return {"status": "ok"}


@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie("admin_session")
    return {"status": "ok"}


# --------- Supplier Directory ---------
@app.get("/api/admin/suppliers", response_model=List[SupplierOut])
def list_suppliers(
    q: str = "",
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    stmt = select(Supplier)
    if q:
        stmt = stmt.where(Supplier.supplier.ilike(f"%{q}%") | Supplier.inn.ilike(f"%{q}%"))
    stmt = stmt.order_by(Supplier.supplier)
    return session.exec(stmt).all()


@app.post("/api/admin/suppliers", response_model=SupplierOut)
def create_supplier(
    payload: SupplierCreate,
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    supplier = Supplier(**payload.dict(), created_at=datetime.utcnow())
    session.add(supplier)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate supplier")
    session.refresh(supplier)
    return supplier


@app.put("/api/admin/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(supplier, field, value)
    supplier.created_at = supplier.created_at or datetime.utcnow()
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier


@app.delete("/api/admin/suppliers/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    session.delete(supplier)
    session.commit()
    return {"status": "deleted"}


# --------- Moderation ---------
@app.get("/api/admin/mappings/pending", response_model=List[MappingModerationResponse])
def list_pending_mappings(
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    stmt = (
        select(SupplierMapping)
        .where(SupplierMapping.status == SupplierMappingStatus.PENDING)
        .order_by(SupplierMapping.created_at)
    )
    mappings = session.exec(stmt).all()
    result: List[MappingModerationResponse] = []
    for m in mappings:
        result.append(
            MappingModerationResponse(
                id=m.id,
                owner_id=m.owner_id,
                packet_id=m.packet_id,
                inn_norm=m.inn_norm,
                std_supplier_raw=m.std_supplier_raw,
                status=m.status,
                canonical_supplier_id=m.canonical_supplier_id,
                canonical_supplier=m.canonical_supplier.supplier if m.canonical_supplier else "",
                created_at=m.created_at,
            )
        )
    return result


@app.post("/api/admin/mappings/{mapping_id}/approve")
def approve_mapping(
    mapping_id: int,
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    mapping = session.get(SupplierMapping, mapping_id)
    if not mapping or mapping.status != SupplierMappingStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not pending")
    mapping.status = SupplierMappingStatus.APPROVED
    mapping.approved_at = datetime.utcnow()
    mapping.approved_by = admin
    mapping.updated_at = datetime.utcnow()
    session.add(mapping)
    log_moderation_event(session, mapping, ModerationDecision.APPROVED, admin_user=admin)
    session.commit()
    return {"status": "APPROVED"}


@app.post("/api/admin/mappings/{mapping_id}/reject")
def reject_mapping(
    mapping_id: int,
    payload: Optional[RejectRequest] = None,
    reason: Optional[str] = None,
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    mapping = session.get(SupplierMapping, mapping_id)
    if not mapping or mapping.status != SupplierMappingStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not pending")
    reason_code = payload.reason_code if payload else reason
    if not reason_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reject reason required")
    reason_label = REJECTION_REASONS.get(reason_code, reason_code)
    mapping.status = SupplierMappingStatus.REJECTED
    mapping.rejected_at = datetime.utcnow()
    mapping.rejected_by = admin
    mapping.updated_at = datetime.utcnow()
    mapping.reject_reason = reason_code
    session.add(mapping)
    log_moderation_event(
        session,
        mapping,
        ModerationDecision.REJECTED,
        admin_user=admin,
        reject_reason_code=reason_code,
        reject_comment_internal=payload.comment_internal if payload else None,
    )
    session.commit()
    return {"status": "REJECTED", "reason_label": reason_label}


@app.get("/api/admin/moderation/history", response_model=List[ModerationEventOut])
def moderation_history(
    limit: int = 50,
    offset: int = 0,
    q: str = "",
    admin: str = Depends(get_admin_user),
    session: Session = Depends(get_session),
):
    stmt = (
        select(ModerationEvent, SupplierMapping, Supplier, PriceSupplierGroup)
        .join(SupplierMapping, ModerationEvent.mapping_id == SupplierMapping.id, isouter=True)
        .join(Supplier, Supplier.id == SupplierMapping.canonical_supplier_id, isouter=True)
        .join(PriceSupplierGroup, PriceSupplierGroup.id == ModerationEvent.supplier_group_id, isouter=True)
    )
    if q:
        stmt = stmt.where(or_(ModerationEvent.owner_id.ilike(f"%{q}%"), ModerationEvent.packet_id.ilike(f"%{q}%")))
    stmt = stmt.order_by(ModerationEvent.decided_at.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    results: List[ModerationEventOut] = []
    for ev, mapping, supplier, group in rows:
        results.append(
            ModerationEventOut(
                id=ev.id,
                owner_id=ev.owner_id,
                packet_id=ev.packet_id,
                supplier_group_id=ev.supplier_group_id,
                decision=ev.decision,
                decided_at=ev.decided_at,
                decided_by=ev.decided_by,
                reject_reason_label=ev.reject_reason_label,
                reject_comment_internal=ev.reject_comment_internal,
                std_supplier_raw=group.std_supplier_raw if group else None,
                inn_norm=group.inn_norm if group else None,
                packet=group.packet_id if group else ev.packet_id,
                canonical_supplier=supplier.supplier if supplier else None,
                canonical_inn=supplier.inn if supplier else None,
                canonical_city=supplier.city if supplier else None,
                status=mapping.status if mapping else None,
            )
        )
    return results


# --------- Issues ---------
@app.get("/api/admin/issues", response_model=List[IssueOut])
def list_issues(admin: str = Depends(get_admin_user), session: Session = Depends(get_session)):
    stmt = select(SellerIssue).order_by(SellerIssue.created_at.desc())
    return session.exec(stmt).all()


# --------- Analytics ---------
@app.get("/api/analytics/mappings", response_model=List[AnalyticsMappingOut])
def analytics_mappings(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    session: Session = Depends(get_session),
):
    stmt = select(SupplierMapping).where(SupplierMapping.status == SupplierMappingStatus.APPROVED)
    if from_date:
        stmt = stmt.where(SupplierMapping.approved_at >= datetime.fromisoformat(from_date))
    if to_date:
        stmt = stmt.where(SupplierMapping.approved_at <= datetime.fromisoformat(to_date))
    mappings = session.exec(stmt).all()
    result: List[AnalyticsMappingOut] = []
    for m in mappings:
        result.append(
            AnalyticsMappingOut(
                ownerId=m.owner_id,
                packetId=m.packet_id,
                inn=m.inn_norm,
                std_supplier_raw=m.std_supplier_raw,
                canonical_supplier_id=m.canonical_supplier_id,
                canonical_supplier=m.canonical_supplier.supplier if m.canonical_supplier else "",
                approved_at=m.approved_at or m.updated_at,
            )
        )
    return result


@app.get("/api/analytics/mappings/by_packet", response_model=List[AnalyticsMappingOut])
def analytics_by_packet(
    packetId: str,
    ownerId: str,
    session: Session = Depends(get_session),
):
    stmt = select(SupplierMapping).where(
        SupplierMapping.status == SupplierMappingStatus.APPROVED,
        SupplierMapping.packet_id == packetId,
        SupplierMapping.owner_id == ownerId,
    )
    mappings = session.exec(stmt).all()
    return [
        AnalyticsMappingOut(
            ownerId=m.owner_id,
            packetId=m.packet_id,
            inn=m.inn_norm,
            std_supplier_raw=m.std_supplier_raw,
            canonical_supplier_id=m.canonical_supplier_id,
            canonical_supplier=m.canonical_supplier.supplier if m.canonical_supplier else "",
            approved_at=m.approved_at or m.updated_at,
        )
        for m in mappings
    ]
