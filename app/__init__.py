from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.admin import admin_bp
from app.auth import auth_bp
from app.config import Config, INSTANCE_DIR
from app.extensions import csrf, db, login_manager
from app.models import Area, ServiceRequest, Table, TableSession, User, ensure_customer_schema, utc_now
from app.permissions import staff_required
from app.reports import reports_bp
from app.services import (
    SERVICE_REQUEST_TYPE_LABELS,
    assign_table,
    build_service_request_api_row,
    clear_table,
    complete_service_request,
    create_service_request_from_qr,
    get_active_service_requests,
    get_active_session_for_table,
    mark_service_request_seen,
    transfer_table,
)


DISPLAY_TIMEZONE = ZoneInfo("Europe/Istanbul")


def create_empty_dashboard_data():
    return {
        "total_tables": 0,
        "occupied_tables": 0,
        "empty_tables": 0,
        "general_occupancy_rate": 0,
        "area_cards": [],
        "recommended_tables": [],
    }


def normalize_datetime_as_utc(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def format_datetime_for_display(value):
    normalized_value = normalize_datetime_as_utc(value)

    if normalized_value is None:
        return "-"

    local_value = normalized_value.astimezone(DISPLAY_TIMEZONE)

    return local_value.strftime("%d.%m.%Y %H:%M")


def format_duration_from_minutes(duration_minutes):
    if duration_minutes is None:
        return "-"

    if duration_minutes < 1:
        return "0 dk"

    hours = duration_minutes // 60
    minutes = duration_minutes % 60

    if hours == 0:
        return f"{minutes} dk"

    if minutes == 0:
        return f"{hours} sa"

    return f"{hours} sa {minutes} dk"


def calculate_active_duration_text(check_in_at):
    normalized_check_in_at = normalize_datetime_as_utc(check_in_at)

    if normalized_check_in_at is None:
        return "-"

    duration_seconds = (utc_now() - normalized_check_in_at).total_seconds()
    duration_minutes = int(duration_seconds // 60)

    if duration_minutes < 0:
        duration_minutes = 0

    return format_duration_from_minutes(duration_minutes)


def get_active_session_map():
    active_sessions = TableSession.query.filter_by(
        status=TableSession.STATUS_ACTIVE,
    ).all()

    return {
        active_session.table_id: active_session
        for active_session in active_sessions
    }



def get_active_service_request_map():
    active_service_requests = get_active_service_requests()
    service_request_map = {}

    for service_request in active_service_requests:
        service_request_map.setdefault(service_request.table_id, []).append(service_request)

    return service_request_map


def build_table_service_request_summary(service_requests):
    if not service_requests:
        return {
            "count": 0,
            "label": "",
            "status": "",
        }

    first_request = service_requests[0]
    count = len(service_requests)
    request_label = SERVICE_REQUEST_TYPE_LABELS.get(
        first_request.request_type,
        first_request.request_type,
    )

    if count > 1:
        request_label = f"{count} çağrı"

    return {
        "count": count,
        "label": request_label,
        "status": first_request.status,
    }

def build_table_view_model(table, active_session=None, service_requests=None):
    customer_count = None
    party_size = ""
    customer_name = ""
    customer_phone = ""
    note = ""
    check_in_display = ""
    duration = "-"
    service_request_summary = build_table_service_request_summary(service_requests or [])

    if active_session is not None:
        customer_count = active_session.party_size
        party_size = active_session.party_size
        customer_name = active_session.customer_name or ""
        customer_phone = active_session.customer_phone or ""
        note = active_session.note or ""
        check_in_display = format_datetime_for_display(active_session.check_in_at)
        duration = calculate_active_duration_text(active_session.check_in_at)

    return {
        "id": table.id,
        "code": table.code,
        "area_key": table.area.slug,
        "area_name": table.area.name,
        "capacity": table.capacity,
        "status": table.status,
        "customer_count": customer_count,
        "party_size": party_size,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "note": note,
        "check_in_display": check_in_display,
        "duration": duration,
        "service_request_count": service_request_summary["count"],
        "service_request_label": service_request_summary["label"],
        "service_request_status": service_request_summary["status"],
    }


def calculate_dashboard_data(tables, areas):
    active_tables = [table for table in tables if table["status"] != Table.STATUS_INACTIVE]
    occupied_tables = [
        table
        for table in active_tables
        if table["status"] in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]
    ]
    empty_tables = [
        table for table in active_tables if table["status"] == Table.STATUS_EMPTY
    ]

    total_active = len(active_tables)
    occupied_count = len(occupied_tables)
    empty_count = len(empty_tables)

    general_occupancy_rate = 0

    if total_active > 0:
        general_occupancy_rate = round((occupied_count / total_active) * 100, 1)

    area_cards = []

    for area in areas:
        area_tables = [
            table
            for table in tables
            if table["area_key"] == area.slug and table["status"] != Table.STATUS_INACTIVE
        ]
        area_occupied_tables = [
            table
            for table in area_tables
            if table["status"] in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]
        ]
        area_empty_tables = [
            table for table in area_tables if table["status"] == Table.STATUS_EMPTY
        ]

        area_total = len(area_tables)
        area_occupied = len(area_occupied_tables)
        area_empty = len(area_empty_tables)

        area_occupancy_rate = 0

        if area_total > 0:
            area_occupancy_rate = round((area_occupied / area_total) * 100, 1)

        area_cards.append(
            {
                "key": area.slug,
                "name": area.name,
                "total": area_total,
                "occupied": area_occupied,
                "empty": area_empty,
                "occupancy_rate": area_occupancy_rate,
            }
        )

    return {
        "total_tables": total_active,
        "occupied_tables": occupied_count,
        "empty_tables": empty_count,
        "general_occupancy_rate": general_occupancy_rate,
        "area_cards": area_cards,
        "recommended_tables": [],
    }


def get_dashboard_context():
    areas = Area.query.filter_by(is_active=True).order_by(Area.display_order.asc()).all()

    table_records = (
        Table.query.join(Area)
        .filter(Area.is_active.is_(True))
        .order_by(Area.display_order.asc(), Table.sort_order.asc())
        .all()
    )

    active_session_map = get_active_session_map()
    service_request_map = get_active_service_request_map()

    tables = [
        build_table_view_model(
            table_record,
            active_session_map.get(table_record.id),
            service_request_map.get(table_record.id, []),
        )
        for table_record in table_records
    ]

    dashboard_data = calculate_dashboard_data(tables, areas)

    return tables, dashboard_data


def create_error_response(message, status_code=400):
    response = {
        "success": False,
        "message": message,
    }

    return jsonify(response), status_code


def create_app():
    app = Flask(
        __name__,
        instance_path=str(INSTANCE_DIR),
        instance_relative_config=True,
    )

    app.config.from_object(Config)

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Devam etmek için giriş yapmalısınız."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            parsed_user_id = int(user_id)
        except (TypeError, ValueError):
            return None

        return db.session.get(User, parsed_user_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return create_error_response("Bu işlem için giriş yapmalısınız.", 401)

        return redirect(url_for("auth.login", next=request.full_path))

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    with app.app_context():
        ensure_customer_schema()

    @app.before_request
    def enforce_default_password_change():
        if not current_user.is_authenticated:
            return None

        if not current_user.is_default_password:
            return None

        allowed_endpoints = {
            "auth.change_password",
            "auth.logout",
            "static",
        }

        if request.endpoint in allowed_endpoints:
            return None

        if request.path.startswith("/static/"):
            return None

        if request.path.startswith("/api/"):
            return create_error_response(
                "Varsayılan şifre değiştirilmeden işlem yapılamaz.",
                403,
            )

        return redirect(url_for("auth.change_password"))

    @app.route("/")
    @login_required
    def index():
        database_not_ready = False

        try:
            tables, dashboard_data = get_dashboard_context()
        except SQLAlchemyError:
            db.session.rollback()
            tables = []
            dashboard_data = create_empty_dashboard_data()
            database_not_ready = True

        return render_template(
            "dashboard.html",
            app_name=app.config["APP_NAME"],
            tables=tables,
            dashboard_data=dashboard_data,
            database_not_ready=database_not_ready,
        )

    @app.post("/api/tables/assign")
    @staff_required
    def assign_table_api():
        payload = request.get_json(silent=True) or {}

        table_id = payload.get("table_id")
        party_size = payload.get("party_size")
        customer_name = payload.get("customer_name")
        customer_phone = payload.get("customer_phone")
        note = payload.get("note")

        try:
            table_session = assign_table(
                table_id=table_id,
                party_size=party_size,
                customer_name=customer_name,
                customer_phone=customer_phone,
                note=note,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Masa atama sırasında veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Masa atama işlemi tamamlandı.",
                "table_session_id": table_session.id,
            }
        )

    @app.post("/api/tables/clear")
    @staff_required
    def clear_table_api():
        payload = request.get_json(silent=True) or {}

        table_id = payload.get("table_id")

        try:
            table_session = clear_table(
                table_id=table_id,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Masa boşaltma sırasında veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Masa boşaltma işlemi tamamlandı.",
                "table_session_id": table_session.id,
                "duration_minutes": table_session.duration_minutes,
            }
        )

    @app.post("/api/tables/transfer")
    @staff_required
    def transfer_table_api():
        payload = request.get_json(silent=True) or {}

        source_table_id = payload.get("source_table_id")
        target_table_id = payload.get("target_table_id")

        try:
            table_session = transfer_table(
                source_table_id=source_table_id,
                target_table_id=target_table_id,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Masa transferi sırasında veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Masa transferi tamamlandı.",
                "table_session_id": table_session.id,
            }
        )

    return app