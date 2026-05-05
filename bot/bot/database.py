from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    String, Integer, BigInteger, DateTime, Text, Boolean, JSON,
    ForeignKey, select, update, func, Index, UniqueConstraint, CheckConstraint, event, text
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.exc import IntegrityError

from .config import SETTINGS, logger  # log uchun

# -------------------------
# Admin cache (in-memory)
# -------------------------
_admin_cache: set[int] = set()


def is_admin(uid: int) -> bool:
    """Check if user is any type of admin (superadmin or DB admin)."""
    return uid in _admin_cache


def is_superadmin(uid: int) -> bool:
    """Check if user is a superadmin (from .env)."""
    return uid in SETTINGS.admin_ids


def get_all_admin_ids() -> set[int]:
    """Return a copy of all admin IDs (superadmin + DB admins)."""
    return _admin_cache.copy()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# -------------------------
# Models
# -------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(128), default="", server_default="", index=True)
    full_name: Mapped[str] = mapped_column(String(256), default="", server_default="")
    balance: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)

    has_used_free_trial: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    daily_limit: Mapped[int] = mapped_column(Integer, default=5, server_default="5")

    referral_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)

    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user")
    language_code: Mapped[str] = mapped_column(String(8), default="uz", server_default="uz")
    total_spent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    referred_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    referral_tier: Mapped[str] = mapped_column(String(16), default="level1", server_default="level1")
    plan: Mapped[str] = mapped_column(String(32), default="free", server_default="free")
    total_documents: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_orders: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    time_saved: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    academic_context: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    vip_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    # ✅ MUHIM: relationship kolleksiya bo'lsa list[...] bo'lishi kerak (Sequence emas)
    requests: Mapped[list["Request"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(512))
    title_topic: Mapped[str] = mapped_column(String(512), default="", server_default="")
    language: Mapped[str] = mapped_column(String(16), index=True)
    level: Mapped[str] = mapped_column(String(32), default="standard", server_default="standard", index=True)

    length: Mapped[str] = mapped_column(String(8), default="1", server_default="1")
    price: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    requirements_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="", server_default="")
    custom_structure: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="", server_default="")
    export_format: Mapped[str] = mapped_column(String(16), default="docx", server_default="docx")



    citation_style: Mapped[str] = mapped_column(String(32), default="APA", server_default="APA")

    quality_score: Mapped[float] = mapped_column(default=0.0, server_default="0.0")
    meta_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    result_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        default="queued",
        server_default="queued",
        index=True,
    )

    current_step: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_steps: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    result_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    download_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    locked_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )

    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="requests", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("download_token", name="uq_requests_download_token"),
        Index("ix_requests_user_status", "user_id", "status"),
        CheckConstraint(
            "status IN ('queued','processing','done','error')",
            name="ck_requests_status",
        ),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    invoice_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    amount: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    screenshot_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="payments", lazy="selectin")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ✅ yaxshiroq: user bilan FK bog'lash
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    ticket_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(256))
    message: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), default="open", server_default="open", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class Catalog(Base):
    __tablename__ = "catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512))
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    language: Mapped[str] = mapped_column(String(16), index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    price: Mapped[int] = mapped_column(Integer, default=5000, server_default="5000")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    amount: Mapped[int] = mapped_column(Integer)
    uses_left: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), default="", server_default="")


class PaymentAdminMessage(Base):
    """Telegram message IDs sent to admins for a payment notification."""
    __tablename__ = "payment_admin_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(Integer)
    invoice_id: Mapped[str] = mapped_column(String(64))
    admin_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentCard(Base):
    """Bank cards shown to users on the top-up flow.

    Owned by the NestJS backend's Prisma schema; we just read from it here.
    """
    __tablename__ = "payment_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(32))
    holder: Mapped[str] = mapped_column(String(128))
    bank: Mapped[str] = mapped_column(String(64), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# -------------------------
# Engine / Session
# -------------------------
engine = create_async_engine(
    SETTINGS.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=50,  # Increased for better concurrency
    max_overflow=20,  # Maximum overflow connections
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# SQLite-only pragmas (skip when using PostgreSQL)
if SETTINGS.database_url.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_on_connect(dbapi_connection, connection_record):  # type: ignore
        """Configures SQLite connection with optimal settings."""
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.close()
        except Exception as e:
            logger.warning("Failed to set SQLite pragmas: %s", e)


AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _sync_table_columns(conn, table_name: str, model_class: type[Base]) -> None:
    """
    SQLite-da mavjud jadvallarga yangi ustunlarni avtomatik qo'shadi (Migration o'rniga).
    """
    try:
        from sqlalchemy import text
        res = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        physical_cols = {row[1] for row in res.fetchall()}
        
        # Base.metadata orqali model ustunlarini olamiz
        model_cols = model_class.__table__.columns
        
        for col_name, col_obj in model_cols.items():
            if col_name not in physical_cols:
                type_str = str(col_obj.type).upper()
                if "VARCHAR" in type_str: type_str = "VARCHAR(256)"
                if "JSON" in type_str: type_str = "TEXT"
                if "BOOLEAN" in type_str: type_str = "BOOLEAN DEFAULT 0"
                if "INTEGER" in type_str: type_str = "INTEGER DEFAULT 0"
                
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {type_str}"))
                logger.info(f"Database Sync: '{table_name}' jadvaliga '{col_name}' ustuni qo'shildi.")
    except Exception as e:
        logger.error(f"Database Sync Error ({table_name}): {e}")


async def init_db() -> None:
    is_sqlite = SETTINGS.database_url.startswith("sqlite")
    async with engine.begin() as conn:
        if is_sqlite:
            # SQLite: dev fallback — auto-create + auto-migrate
            await conn.run_sync(Base.metadata.create_all)
            await _sync_table_columns(conn, "users", User)
            await _sync_table_columns(conn, "requests", Request)
        # On PostgreSQL the schema is owned by Prisma migrations (NestJS backend).
        # We just confirm we can connect.
        
    logger.info("Database: Initialization complete.")


# -------------------------
# DB helpers
# -------------------------
class DB:
    @staticmethod
    async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
        res = await session.execute(select(User).where(User.id == user_id))
        return res.scalar_one_or_none()

    @staticmethod
    async def upsert_user(session: AsyncSession, user_id: int, username: str = "", full_name: str = "") -> User:
        user = await DB.get_user(session, user_id)
        if user:
            user.username = username or user.username
            user.full_name = full_name or user.full_name
            await session.commit()
            return user

        try:
            user = User(id=user_id, username=username or "", full_name=full_name or "")
            session.add(user)
            await session.commit()
            return user
        except IntegrityError:
            await session.rollback()
            user2 = await DB.get_user(session, user_id)
            if user2:
                return user2
            raise

    @staticmethod
    async def get_request(session: AsyncSession, req_id: int) -> Optional[Request]:
        res = await session.execute(select(Request).where(Request.id == req_id))
        return res.scalar_one_or_none()

    @staticmethod
    async def get_request_by_token(session: AsyncSession, token: str) -> Optional[Request]:
        res = await session.execute(select(Request).where(Request.download_token == token))
        return res.scalar_one_or_none()

    @staticmethod
    async def update_balance(session: AsyncSession, user_id: int, delta: int) -> bool:
        result = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(balance=User.balance + delta, updated_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        return (result.rowcount or 0) > 0

    @staticmethod
    async def toggle_block(session: AsyncSession, user_id: int, status: bool) -> bool:
        result = await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_blocked=bool(status), updated_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        return (result.rowcount or 0) > 0

    @staticmethod
    async def claim_request(session: AsyncSession, req_id: int, worker_id: str) -> bool:
        result = await session.execute(
            update(Request)
            .where(Request.id == req_id)
            .where(Request.status == "queued")
            .values(
                status="processing",
                locked_by=worker_id,
                locked_at=utcnow(),
                attempts=Request.attempts + 1,
                updated_at=utcnow(),
            )
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        return (result.rowcount or 0) == 1

    @staticmethod
    async def recover_processing_to_queued(session: AsyncSession) -> int:
        result = await session.execute(
            update(Request)
            .where(Request.status == "processing")
            .values(status="queued", locked_by=None, locked_at=None, updated_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        return int(result.rowcount or 0)

    @staticmethod
    async def mark_request_done(
        session: AsyncSession,
        req_id: int,
        *,
        result_path: str,
        result_file_id: Optional[str] = None,
        download_token: str,
        expires_at: datetime,
    ) -> None:
        result = await session.execute(
            update(Request)
            .where(Request.id == req_id)
            .values(
                status="done",
                result_path=result_path,
                result_file_id=result_file_id,
                download_token=download_token,
                expires_at=expires_at,
                error_log=None,
                locked_by=None,
                locked_at=None,
                updated_at=utcnow(),
            )
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        if (result.rowcount or 0) == 0:
            logger.warning("mark_request_done: request #%s not found", req_id)

    @staticmethod
    async def mark_request_error(session: AsyncSession, req_id: int, error_log: str) -> None:
        result = await session.execute(
            update(Request)
            .where(Request.id == req_id)
            .values(
                status="error",
                error_log=error_log[:20000],
                locked_by=None,
                locked_at=None,
                updated_at=utcnow(),
            )
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        if (result.rowcount or 0) == 0:
            logger.warning("mark_request_error: request #%s not found", req_id)

    @staticmethod
    async def get_setting(session: AsyncSession, key: str) -> str:
        res = await session.execute(select(AppSettings).where(AppSettings.key == key))
        obj = res.scalar_one_or_none()
        return obj.value if obj else ""

    @staticmethod
    async def set_setting(session: AsyncSession, key: str, value: str) -> None:
        res = await session.execute(select(AppSettings).where(AppSettings.key == key))
        obj = res.scalar_one_or_none()
        if obj:
            obj.value = value
        else:
            session.add(AppSettings(key=key, value=value))
        await session.commit()

    @staticmethod
    async def load_admin_cache(session: AsyncSession) -> set[int]:
        """Startup: load all admin IDs (env + DB) into in-memory cache."""
        global _admin_cache
        _admin_cache = set(SETTINGS.admin_ids)
        res = await session.execute(
            select(User.id).where(User.role == "admin")
        )
        db_admins = res.scalars().all()
        _admin_cache.update(db_admins)
        return _admin_cache

    @staticmethod
    async def add_admin(session: AsyncSession, uid: int) -> None:
        """Grant admin role to a user and update cache."""
        global _admin_cache
        user = await DB.get_user(session, uid)
        if not user:
            raise ValueError(f"User {uid} topilmadi")
        user.role = "admin"
        await session.commit()
        _admin_cache.add(uid)

    @staticmethod
    async def remove_admin(session: AsyncSession, uid: int) -> None:
        """Remove admin role from a user and update cache."""
        global _admin_cache
        if uid in SETTINGS.admin_ids:
            raise ValueError("Superadminni o'chirib bo'lmaydi")
        user = await DB.get_user(session, uid)
        if user:
            user.role = "user"
            await session.commit()
        _admin_cache.discard(uid)

    @staticmethod
    async def list_admins(session: AsyncSession) -> list[User]:
        """Return all users with admin role."""
        res = await session.execute(
            select(User).where(User.role == "admin")
        )
        return list(res.scalars().all())

    @staticmethod
    async def list_active_payment_cards(session: AsyncSession) -> list[PaymentCard]:
        """Return active payment cards in display order."""
        res = await session.execute(
            select(PaymentCard)
            .where(PaymentCard.is_active.is_(True))
            .order_by(PaymentCard.sort_order.asc(), PaymentCard.id.asc())
        )
        return list(res.scalars().all())

    @staticmethod
    async def get_payment_by_invoice(session: AsyncSession, invoice_id: str) -> Optional[Payment]:
        res = await session.execute(select(Payment).where(Payment.invoice_id == invoice_id))
        return res.scalar_one_or_none()

    @staticmethod
    async def update_payment_status(session: AsyncSession, invoice_id: str, status: str) -> bool:
        result = await session.execute(
            update(Payment)
            .where(Payment.invoice_id == invoice_id)
            .values(status=status)
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        return (result.rowcount or 0) > 0
