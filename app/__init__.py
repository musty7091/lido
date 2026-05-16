from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app.admin import admin_bp
from app.auth import auth_bp
from app.config import Config, INSTANCE_DIR
from app.extensions import csrf, db, login_manager
from app.models import Area, Reservation, ServiceRequest, Table, TableSession, User, ensure_customer_schema, utc_now
from app.permissions import admin_required, staff_required
from app.reports import reports_bp
from app.services import (
    SERVICE_REQUEST_TYPE_LABELS,
    assign_table,
    build_service_request_api_row,
    clear_table,
    complete_service_request,
    create_reservation,
    update_reservation,
    cancel_reservation,
    create_service_request_from_qr,
    get_active_service_requests,
    get_active_session_for_table,
    mark_service_request_seen,
    transfer_table,
)


DISPLAY_TIMEZONE = ZoneInfo("Europe/Istanbul")


def get_safe_redirect_url(value):
    cleaned_value = str(value or "").strip()

    if cleaned_value.startswith("/") and not cleaned_value.startswith("//"):
        return cleaned_value

    return url_for("index")


def get_table_status_label(status):
    status_labels = {
        Table.STATUS_EMPTY: "Boş",
        Table.STATUS_OCCUPIED: "Dolu",
        Table.STATUS_LONG: "Uzun Süre",
        Table.STATUS_INACTIVE: "Pasif",
    }

    return status_labels.get(status, status or "-")


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

    return value.astimezone(timezone.utc)


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

def format_time_for_display(value):
    normalized_value = normalize_datetime_as_utc(value)

    if normalized_value is None:
        return "-"

    local_value = normalized_value.astimezone(DISPLAY_TIMEZONE)

    return local_value.strftime("%H:%M")


def format_tl_for_display(value):
    if value is None:
        return "Kapora yok"

    try:
        normalized_value = float(value)
    except (TypeError, ValueError):
        return f"{value} TL"

    formatted_value = f"{normalized_value:,.2f}"
    formatted_value = (
        formatted_value
        .replace(",", "TEMP")
        .replace(".", ",")
        .replace("TEMP", ".")
    )

    if formatted_value.endswith(",00"):
        formatted_value = formatted_value[:-3]

    return f"{formatted_value} TL"


def build_empty_reservation_summary():
    return {
        "has_reservation": False,
        "reservation_id": "",
        "reservation_state": "",
        "reservation_state_label": "",
        "reservation_badge_label": "",
        "reservation_time_label": "",
        "reservation_display": "",
        "reservation_date_value": "",
        "reservation_time_value": "",
        "reservation_duration_minutes": "",
        "reservation_customer_name": "",
        "reservation_customer_phone": "",
        "reservation_party_size": "",
        "reservation_deposit_display": "",
        "reservation_deposit_amount_value": "",
        "reservation_deposit_note": "",
        "reservation_note": "",
        "reservation_protection_minutes": "",
        "reservation_no_show_tolerance_minutes": "",
        "reservation_blocks_assignment": False,
    }


def build_reservation_summary(reservation, reference_time=None):
    if reservation is None:
        return build_empty_reservation_summary()

    if reference_time is None:
        reference_time = utc_now()

    normalized_reference_time = normalize_datetime_as_utc(reference_time)
    reservation_at = normalize_datetime_as_utc(reservation.reservation_at)

    if reservation_at is None:
        return build_empty_reservation_summary()

    protection_minutes = (
        reservation.protection_minutes
        or Reservation.DEFAULT_PROTECTION_MINUTES
    )
    no_show_tolerance_minutes = (
        reservation.no_show_tolerance_minutes
        or Reservation.DEFAULT_NO_SHOW_TOLERANCE_MINUTES
    )

    protection_start = reservation_at - timedelta(minutes=protection_minutes)
    no_show_deadline = reservation_at + timedelta(minutes=no_show_tolerance_minutes)
    reservation_local = reservation_at.astimezone(DISPLAY_TIMEZONE)
    time_label = format_time_for_display(reservation_at)
    date_value = reservation_local.strftime("%Y-%m-%d")
    time_value = reservation_local.strftime("%H:%M")
    blocks_assignment = protection_start <= normalized_reference_time <= no_show_deadline

    if normalized_reference_time > reservation_at:
        reservation_state = "late"
        reservation_state_label = "Gecikti"
        reservation_badge_label = f"GECİKTİ {time_label}"
    elif normalized_reference_time >= protection_start:
        reservation_state = "protected"
        reservation_state_label = "Koruma Süresinde"
        reservation_badge_label = f"REZERVE {time_label}"
    else:
        reservation_state = "upcoming"
        reservation_state_label = "Yaklaşan Rezervasyon"
        reservation_badge_label = time_label

    return {
        "has_reservation": True,
        "reservation_id": reservation.id,
        "reservation_state": reservation_state,
        "reservation_state_label": reservation_state_label,
        "reservation_badge_label": reservation_badge_label,
        "reservation_time_label": time_label,
        "reservation_display": format_datetime_for_display(reservation_at),
        "reservation_date_value": date_value,
        "reservation_time_value": time_value,
        "reservation_duration_minutes": reservation.duration_minutes or Reservation.DEFAULT_DURATION_MINUTES,
        "reservation_customer_name": reservation.customer_name or "İsimsiz müşteri",
        "reservation_customer_phone": reservation.customer_phone or "-",
        "reservation_party_size": reservation.party_size or "-",
        "reservation_deposit_display": format_tl_for_display(reservation.deposit_amount_tl),
        "reservation_deposit_amount_value": str(reservation.deposit_amount_tl) if reservation.deposit_amount_tl is not None else "",
        "reservation_deposit_note": reservation.deposit_note or "",
        "reservation_note": reservation.note or "",
        "reservation_protection_minutes": protection_minutes,
        "reservation_no_show_tolerance_minutes": no_show_tolerance_minutes,
        "reservation_blocks_assignment": blocks_assignment,
    }


def get_reservation_map(reference_time=None):
    if reference_time is None:
        reference_time = utc_now()

    normalized_reference_time = normalize_datetime_as_utc(reference_time)
    start_limit = normalized_reference_time - timedelta(hours=12)

    confirmed_reservations = (
        Reservation.query
        .filter(
            Reservation.status == Reservation.STATUS_CONFIRMED,
            Reservation.expected_end_at >= start_limit,
        )
        .order_by(Reservation.reservation_at.asc(), Reservation.id.asc())
        .all()
    )

    reservation_map = {}

    for reservation in confirmed_reservations:
        if reservation.table_id in reservation_map:
            continue

        reservation_map[reservation.table_id] = reservation

    return reservation_map


def build_table_view_model(table, active_session=None, service_requests=None, reservation=None):
    customer_count = None
    party_size = ""
    customer_name = ""
    customer_phone = ""
    note = ""
    check_in_display = ""
    duration = "-"
    service_request_summary = build_table_service_request_summary(service_requests or [])
    reservation_summary = build_reservation_summary(reservation)

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
        **reservation_summary,
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
    reservation_map = get_reservation_map()

    tables = [
        build_table_view_model(
            table_record,
            active_session_map.get(table_record.id),
            service_request_map.get(table_record.id, []),
            reservation_map.get(table_record.id),
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

    @app.context_processor
    def inject_reservation_form_data():
        today_local = utc_now().astimezone(DISPLAY_TIMEZONE)
        reservation_defaults = {
            "date": today_local.strftime("%Y-%m-%d"),
            "time": "20:00",
            "duration_minutes": Reservation.DEFAULT_DURATION_MINUTES,
            "duration_hours": int(Reservation.DEFAULT_DURATION_MINUTES / 60),
            "protection_minutes": Reservation.DEFAULT_PROTECTION_MINUTES,
            "no_show_tolerance_minutes": Reservation.DEFAULT_NO_SHOW_TOLERANCE_MINUTES,
        }

        if not current_user.is_authenticated:
            return {
                "reservation_table_choices": [],
                "reservation_defaults": reservation_defaults,
            }

        try:
            table_records = (
                Table.query
                .join(Area)
                .filter(Area.is_active.is_(True))
                .filter(Table.status != Table.STATUS_INACTIVE)
                .order_by(Area.display_order.asc(), Table.sort_order.asc())
                .all()
            )
        except SQLAlchemyError:
            db.session.rollback()
            table_records = []

        reservation_table_choices = [
            {
                "id": table.id,
                "code": table.code,
                "area_name": table.area.name if table.area else "-",
                "capacity": table.capacity,
                "status": table.status,
                "status_label": get_table_status_label(table.status),
            }
            for table in table_records
        ]

        return {
            "reservation_table_choices": reservation_table_choices,
            "reservation_defaults": reservation_defaults,
        }

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

    @app.post("/reservations/create")
    @staff_required
    def create_reservation_form():
        next_url = get_safe_redirect_url(request.form.get("next"))

        try:
            reservation = create_reservation(
                table_id=request.form.get("table_id"),
                reservation_date=request.form.get("reservation_date"),
                reservation_time=request.form.get("reservation_time"),
                party_size=request.form.get("party_size"),
                customer_name=request.form.get("customer_name"),
                customer_phone=request.form.get("customer_phone"),
                deposit_amount_tl=request.form.get("deposit_amount_tl"),
                deposit_note=request.form.get("deposit_note"),
                note=request.form.get("note"),
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Rezervasyon kaydı sırasında veritabanı hatası oluştu.", "danger")
        else:
            reservation_at = normalize_datetime_as_utc(reservation.reservation_at)
            reservation_local = reservation_at.astimezone(DISPLAY_TIMEZONE) if reservation_at else None
            reservation_time_text = reservation_local.strftime("%d.%m.%Y %H:%M") if reservation_local else "-"
            table_code = reservation.table.code if reservation.table else "-"
            flash(
                f"{table_code} masası için {reservation_time_text} rezervasyonu alındı.",
                "success",
            )

        return redirect(next_url)


    @app.post("/api/reservations/<int:reservation_id>/update")
    @admin_required
    def update_reservation_api(reservation_id):
        payload = request.get_json(silent=True) or {}

        try:
            reservation = update_reservation(
                reservation_id=reservation_id,
                table_id=payload.get("table_id"),
                reservation_date=payload.get("reservation_date"),
                reservation_time=payload.get("reservation_time"),
                party_size=payload.get("party_size"),
                customer_name=payload.get("customer_name"),
                customer_phone=payload.get("customer_phone"),
                deposit_amount_tl=payload.get("deposit_amount_tl"),
                deposit_note=payload.get("deposit_note"),
                note=payload.get("note"),
                duration_minutes=payload.get("duration_minutes"),
                protection_minutes=payload.get("protection_minutes"),
                no_show_tolerance_minutes=payload.get("no_show_tolerance_minutes"),
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Rezervasyon güncellenirken veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Rezervasyon güncellendi.",
                "reservation_id": reservation.id,
            }
        )


    @app.post("/api/reservations/<int:reservation_id>/cancel")
    @admin_required
    def cancel_reservation_api(reservation_id):
        payload = request.get_json(silent=True) or {}
        cancel_reason = payload.get("cancel_reason")

        try:
            reservation = cancel_reservation(
                reservation_id=reservation_id,
                cancel_reason=cancel_reason,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Rezervasyon iptal edilirken veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Rezervasyon iptal edildi.",
                "reservation_id": reservation.id,
            }
        )



    @app.route("/qr/t/<qr_token>", methods=["GET", "POST"])
    def public_service_request(qr_token):
        table = Table.query.filter_by(qr_token=qr_token).first()
        request_type_choices = [
            {
                "value": request_type,
                "label": request_type_label,
            }
            for request_type, request_type_label in SERVICE_REQUEST_TYPE_LABELS.items()
        ]

        form_status = None
        message = ""
        selected_type = ""

        if table is None:
            form_status = "error"
            message = "Bu QR kod sisteme kayıtlı bir masaya ait değil."
        elif request.method == "POST":
            selected_type = request.form.get("request_type", "")
            note = request.form.get("note", "")

            try:
                service_request, created = create_service_request_from_qr(
                    qr_token=qr_token,
                    request_type=selected_type,
                    note=note,
                )
            except ValueError as exc:
                db.session.rollback()
                form_status = "error"
                message = str(exc)
            except SQLAlchemyError:
                db.session.rollback()
                form_status = "error"
                message = "Talep kaydedilirken veritabanı hatası oluştu."
            else:
                form_status = "success"
                request_type_label = SERVICE_REQUEST_TYPE_LABELS.get(
                    service_request.request_type,
                    "Servis çağrısı",
                )

                if created:
                    message = f"{request_type_label} talebiniz personele iletildi."
                else:
                    message = (
                        f"Bu masa için açık {request_type_label} talebi zaten var. "
                        "Personel en kısa sürede ilgilenecek."
                    )

        return render_template(
            "service_request_public.html",
            app_name=app.config["APP_NAME"],
            table=table,
            request_type_choices=request_type_choices,
            form_status=form_status,
            message=message,
            selected_type=selected_type,
        )

    @app.get("/api/service-requests/active")
    @staff_required
    def active_service_requests_api():
        active_service_requests = get_active_service_requests()
        service_request_rows = [
            build_service_request_api_row(service_request)
            for service_request in active_service_requests
        ]

        return jsonify(
            {
                "success": True,
                "count": len(service_request_rows),
                "service_requests": service_request_rows,
            }
        )

    @app.post("/api/service-requests/<int:service_request_id>/seen")
    @staff_required
    def mark_service_request_seen_api(service_request_id):
        try:
            service_request = mark_service_request_seen(
                service_request_id=service_request_id,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Servis çağrısı güncellenirken veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Servis çağrısı görüldü olarak işaretlendi.",
                "service_request": build_service_request_api_row(service_request),
            }
        )

    @app.post("/api/service-requests/<int:service_request_id>/complete")
    @staff_required
    def complete_service_request_api(service_request_id):
        try:
            service_request = complete_service_request(
                service_request_id=service_request_id,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
            )
        except ValueError as exc:
            db.session.rollback()
            return create_error_response(str(exc), 400)
        except SQLAlchemyError:
            db.session.rollback()
            return create_error_response("Servis çağrısı tamamlanırken veritabanı hatası oluştu.", 500)

        return jsonify(
            {
                "success": True,
                "message": "Servis çağrısı tamamlandı.",
                "service_request": build_service_request_api_row(service_request),
            }
        )
    return app