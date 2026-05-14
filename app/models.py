from datetime import datetime, timezone

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


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


class TableSession(db.Model):
    __tablename__ = "table_sessions"

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)

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