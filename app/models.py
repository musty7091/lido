from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLE_ADMIN = "admin"
    ROLE_DOOR_STAFF = "door_staff"
    ROLE_BAR_STAFF = "bar_staff"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default=ROLE_BAR_STAFF)

    password_hash = db.Column(db.String(255), nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_default_password = db.Column(db.Boolean, nullable=False, default=False)

    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_label(self):
        role_labels = {
            self.ROLE_ADMIN: "Yönetici",
            self.ROLE_DOOR_STAFF: "Kapı Personeli",
            self.ROLE_BAR_STAFF: "Bar Personeli",
        }

        return role_labels.get(self.role, self.role)

    def __repr__(self):
        return f"<User {self.username}>"


class Area(db.Model):
    __tablename__ = "areas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(50), nullable=False, unique=True)
    prefix = db.Column(db.String(10), nullable=False)
    table_count = db.Column(db.Integer, nullable=False, default=0)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    tables = db.relationship(
        "Table",
        back_populates="area",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __repr__(self):
        return f"<Area {self.name}>"


class Table(db.Model):
    __tablename__ = "tables"

    STATUS_EMPTY = "empty"
    STATUS_OCCUPIED = "occupied"
    STATUS_LONG = "long"
    STATUS_INACTIVE = "inactive"

    id = db.Column(db.Integer, primary_key=True)
    area_id = db.Column(db.Integer, db.ForeignKey("areas.id"), nullable=False)

    code = db.Column(db.String(20), nullable=False, unique=True)
    number = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=4)
    status = db.Column(db.String(20), nullable=False, default=STATUS_EMPTY)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    area = db.relationship("Area", back_populates="tables")
    sessions = db.relationship(
        "TableSession",
        back_populates="table",
        cascade="all, delete-orphan",
        lazy=True,
    )

    __table_args__ = (
        db.UniqueConstraint("area_id", "number", name="uq_tables_area_number"),
    )

    def __repr__(self):
        return f"<Table {self.code}>"


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(120), nullable=True, index=True)
    phone_raw = db.Column(db.String(40), nullable=True)
    phone_normalized = db.Column(db.String(20), nullable=False, unique=True, index=True)
    note = db.Column(db.Text, nullable=True)

    first_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    visit_count = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    sessions = db.relationship(
        "TableSession",
        back_populates="customer",
        lazy=True,
    )

    def __repr__(self):
        return f"<Customer {self.phone_normalized}>"


class TableSession(db.Model):
    __tablename__ = "table_sessions"

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)

    customer_name = db.Column(db.String(120), nullable=True)
    customer_phone = db.Column(db.String(30), nullable=True)
    note = db.Column(db.Text, nullable=True)

    party_size = db.Column(db.Integer, nullable=False)

    check_in_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    check_out_at = db.Column(db.DateTime(timezone=True), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), nullable=False, default=STATUS_ACTIVE)

    opened_by_user_id = db.Column(db.Integer, nullable=True)
    closed_by_user_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    table = db.relationship("Table", back_populates="sessions")
    customer = db.relationship("Customer", back_populates="sessions")

    def __repr__(self):
        return f"<TableSession table_id={self.table_id} status={self.status}>"


class ActionLog(db.Model):
    __tablename__ = "action_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, nullable=True)
    username_snapshot = db.Column(db.String(120), nullable=True)
    role_snapshot = db.Column(db.String(80), nullable=True)

    action_type = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(80), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    target_label = db.Column(db.String(120), nullable=True)

    description = db.Column(db.Text, nullable=False)

    ip_address = db.Column(db.String(80), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    extra_data = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def __repr__(self):
        return f"<ActionLog {self.action_type} {self.created_at}>"


def ensure_customer_schema():
    """
    Mevcut SQLite veritabanını bozmadan müşteri hafızası için gerekli
    tablo ve kolonları hazırlar.

    Projede şu an ayrı bir migration sistemi olmadığı için bu küçük güvence
    uygulama açılışında çalışır:
    - Yeni kurulumda tüm tabloları oluşturur.
    - Eski kurulumda customers tablosunu oluşturur.
    - Eski table_sessions tablosuna customer_id kolonunu ekler.
    """
    db.create_all()

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    if "table_sessions" not in table_names:
        return

    table_session_columns = {
        column["name"]
        for column in inspector.get_columns("table_sessions")
    }

    schema_changed = False

    if "customer_id" not in table_session_columns:
        db.session.execute(
            text("ALTER TABLE table_sessions ADD COLUMN customer_id INTEGER")
        )
        schema_changed = True

    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS "
            "ix_table_sessions_customer_id "
            "ON table_sessions (customer_id)"
        )
    )

    db.session.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ix_customers_phone_normalized "
            "ON customers (phone_normalized)"
        )
    )

    db.session.commit()
