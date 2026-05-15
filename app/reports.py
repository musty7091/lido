from collections import defaultdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, request

from app.models import ActionLog, Area, Table, TableSession, utc_now
from app.permissions import admin_required

reports_bp = Blueprint("admin_reports", __name__, url_prefix="/admin/reports")

DISPLAY_TIMEZONE = ZoneInfo("Europe/Istanbul")


def normalize_datetime_as_utc(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def convert_local_datetime_to_utc(value):
    if value.tzinfo is None:
        local_value = value.replace(tzinfo=DISPLAY_TIMEZONE)
    else:
        local_value = value.astimezone(DISPLAY_TIMEZONE)

    return local_value.astimezone(timezone.utc)


def get_today_local_date():
    return utc_now().astimezone(DISPLAY_TIMEZONE).date()


def parse_selected_date(value):
    if value is None:
        return get_today_local_date()

    cleaned_value = str(value).strip()

    if cleaned_value == "":
        return get_today_local_date()

    try:
        return datetime.strptime(cleaned_value, "%Y-%m-%d").date()
    except ValueError:
        return get_today_local_date()


def build_day_range_utc(selected_date):
    local_start = datetime.combine(selected_date, time.min).replace(tzinfo=DISPLAY_TIMEZONE)
    local_end = datetime.combine(selected_date, time.max).replace(tzinfo=DISPLAY_TIMEZONE)

    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)

    return utc_start, utc_end


def format_date_for_display(value):
    return value.strftime("%d.%m.%Y")


def format_datetime_for_display(value):
    normalized_value = normalize_datetime_as_utc(value)

    if normalized_value is None:
        return "-"

    local_value = normalized_value.astimezone(DISPLAY_TIMEZONE)

    return local_value.strftime("%H:%M")


def format_duration_from_minutes(duration_minutes):
    if duration_minutes is None:
        return "-"

    try:
        parsed_duration = int(duration_minutes)
    except (TypeError, ValueError):
        return "-"

    if parsed_duration < 1:
        return "0 dk"

    hours = parsed_duration // 60
    minutes = parsed_duration % 60

    if hours == 0:
        return f"{minutes} dk"

    if minutes == 0:
        return f"{hours} sa"

    return f"{hours} sa {minutes} dk"


def calculate_active_duration_minutes(check_in_at):
    normalized_check_in_at = normalize_datetime_as_utc(check_in_at)

    if normalized_check_in_at is None:
        return 0

    duration_seconds = (utc_now() - normalized_check_in_at).total_seconds()
    duration_minutes = int(duration_seconds // 60)

    if duration_minutes < 0:
        return 0

    return duration_minutes


def safe_extra_data(action_log):
    if isinstance(action_log.extra_data, dict):
        return action_log.extra_data

    return {}


def get_sessions_started_in_day(day_start_utc, day_end_utc):
    return (
        TableSession.query
        .join(Table, TableSession.table_id == Table.id)
        .join(Area, Table.area_id == Area.id)
        .filter(TableSession.check_in_at >= day_start_utc)
        .filter(TableSession.check_in_at <= day_end_utc)
        .order_by(TableSession.check_in_at.asc(), TableSession.id.asc())
        .all()
    )


def get_sessions_completed_in_day(day_start_utc, day_end_utc):
    return (
        TableSession.query
        .join(Table, TableSession.table_id == Table.id)
        .join(Area, Table.area_id == Area.id)
        .filter(TableSession.status == TableSession.STATUS_COMPLETED)
        .filter(TableSession.check_out_at.isnot(None))
        .filter(TableSession.check_out_at >= day_start_utc)
        .filter(TableSession.check_out_at <= day_end_utc)
        .order_by(TableSession.check_out_at.asc(), TableSession.id.asc())
        .all()
    )


def get_active_sessions():
    return (
        TableSession.query
        .join(Table, TableSession.table_id == Table.id)
        .join(Area, Table.area_id == Area.id)
        .filter(TableSession.status == TableSession.STATUS_ACTIVE)
        .order_by(TableSession.check_in_at.asc(), TableSession.id.asc())
        .all()
    )


def get_action_logs_in_day(day_start_utc, day_end_utc):
    return (
        ActionLog.query
        .filter(ActionLog.created_at >= day_start_utc)
        .filter(ActionLog.created_at <= day_end_utc)
        .order_by(ActionLog.created_at.asc(), ActionLog.id.asc())
        .all()
    )


def calculate_average_duration(completed_sessions):
    durations = [
        session.duration_minutes
        for session in completed_sessions
        if session.duration_minutes is not None
    ]

    if not durations:
        return None

    return round(sum(durations) / len(durations))


def build_area_summary_rows(started_sessions, completed_sessions):
    area_map = defaultdict(
        lambda: {
            "area_name": "",
            "session_count": 0,
            "guest_count": 0,
            "completed_count": 0,
            "total_duration_minutes": 0,
        }
    )

    for session in started_sessions:
        area_name = session.table.area.name
        area_map[area_name]["area_name"] = area_name
        area_map[area_name]["session_count"] += 1
        area_map[area_name]["guest_count"] += session.party_size or 0

    for session in completed_sessions:
        area_name = session.table.area.name
        area_map[area_name]["area_name"] = area_name
        area_map[area_name]["completed_count"] += 1
        area_map[area_name]["total_duration_minutes"] += session.duration_minutes or 0

    rows = []

    for area_data in area_map.values():
        completed_count = area_data["completed_count"]
        average_duration_minutes = None

        if completed_count > 0:
            average_duration_minutes = round(
                area_data["total_duration_minutes"] / completed_count
            )

        rows.append(
            {
                "area_name": area_data["area_name"],
                "session_count": area_data["session_count"],
                "guest_count": area_data["guest_count"],
                "completed_count": completed_count,
                "total_duration": format_duration_from_minutes(
                    area_data["total_duration_minutes"]
                ),
                "average_duration": format_duration_from_minutes(
                    average_duration_minutes
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row["session_count"],
            row["guest_count"],
            row["area_name"],
        ),
        reverse=True,
    )

    return rows


def build_table_summary_rows(started_sessions, completed_sessions):
    table_map = defaultdict(
        lambda: {
            "table_code": "",
            "area_name": "",
            "session_count": 0,
            "guest_count": 0,
            "completed_count": 0,
            "total_duration_minutes": 0,
        }
    )

    for session in started_sessions:
        table_code = session.table.code
        table_map[table_code]["table_code"] = table_code
        table_map[table_code]["area_name"] = session.table.area.name
        table_map[table_code]["session_count"] += 1
        table_map[table_code]["guest_count"] += session.party_size or 0

    for session in completed_sessions:
        table_code = session.table.code
        table_map[table_code]["table_code"] = table_code
        table_map[table_code]["area_name"] = session.table.area.name
        table_map[table_code]["completed_count"] += 1
        table_map[table_code]["total_duration_minutes"] += session.duration_minutes or 0

    rows = []

    for table_data in table_map.values():
        completed_count = table_data["completed_count"]
        average_duration_minutes = None

        if completed_count > 0:
            average_duration_minutes = round(
                table_data["total_duration_minutes"] / completed_count
            )

        rows.append(
            {
                "table_code": table_data["table_code"],
                "area_name": table_data["area_name"],
                "session_count": table_data["session_count"],
                "guest_count": table_data["guest_count"],
                "completed_count": completed_count,
                "total_duration": format_duration_from_minutes(
                    table_data["total_duration_minutes"]
                ),
                "average_duration": format_duration_from_minutes(
                    average_duration_minutes
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row["session_count"],
            row["guest_count"],
            row["table_code"],
        ),
        reverse=True,
    )

    return rows


def build_staff_summary_rows(action_logs):
    operation_types = {
        "table_assigned": "assigned_count",
        "table_cleared": "cleared_count",
        "table_transferred": "transfer_count",
    }

    staff_map = defaultdict(
        lambda: {
            "username": "Sistem",
            "role": "-",
            "assigned_count": 0,
            "cleared_count": 0,
            "transfer_count": 0,
            "total_count": 0,
        }
    )

    for action_log in action_logs:
        if action_log.action_type not in operation_types:
            continue

        username = action_log.username_snapshot or "Sistem"
        role = action_log.role_snapshot or "-"

        staff_map[username]["username"] = username
        staff_map[username]["role"] = role
        staff_map[username][operation_types[action_log.action_type]] += 1
        staff_map[username]["total_count"] += 1

    rows = list(staff_map.values())
    rows.sort(
        key=lambda row: (
            row["total_count"],
            row["assigned_count"],
            row["cleared_count"],
            row["transfer_count"],
            row["username"],
        ),
        reverse=True,
    )

    return rows


def build_transfer_rows(action_logs):
    rows = []

    for action_log in action_logs:
        if action_log.action_type != "table_transferred":
            continue

        extra_data = safe_extra_data(action_log)

        rows.append(
            {
                "time": format_datetime_for_display(action_log.created_at),
                "old_table_code": extra_data.get("old_table_code", "-"),
                "old_area_name": extra_data.get("old_area_name", "-"),
                "new_table_code": extra_data.get("new_table_code", "-"),
                "new_area_name": extra_data.get("new_area_name", "-"),
                "party_size": extra_data.get("party_size", "-"),
                "customer_name": extra_data.get("customer_name") or "-",
                "username": action_log.username_snapshot or "Sistem",
            }
        )

    rows.sort(key=lambda row: row["time"])

    return rows


def build_session_rows(started_sessions):
    rows = []

    for session in started_sessions:
        if session.status == TableSession.STATUS_ACTIVE:
            status_label = "Aktif"
            duration_text = format_duration_from_minutes(
                calculate_active_duration_minutes(session.check_in_at)
            )
            check_out_text = "-"
        elif session.status == TableSession.STATUS_COMPLETED:
            status_label = "Tamamlandı"
            duration_text = format_duration_from_minutes(session.duration_minutes)
            check_out_text = format_datetime_for_display(session.check_out_at)
        else:
            status_label = "İptal"
            duration_text = "-"
            check_out_text = format_datetime_for_display(session.check_out_at)

        rows.append(
            {
                "table_code": session.table.code,
                "area_name": session.table.area.name,
                "party_size": session.party_size,
                "customer_name": session.customer_name or "-",
                "customer_phone": session.customer_phone or "-",
                "check_in": format_datetime_for_display(session.check_in_at),
                "check_out": check_out_text,
                "duration": duration_text,
                "status_label": status_label,
            }
        )

    return rows


def find_most_used_area(area_rows):
    if not area_rows:
        return "-"

    first_row = area_rows[0]

    return (
        f"{first_row['area_name']} "
        f"({first_row['session_count']} oturum / {first_row['guest_count']} kişi)"
    )


def find_most_used_table(table_rows):
    if not table_rows:
        return "-"

    first_row = table_rows[0]

    return (
        f"{first_row['table_code']} "
        f"({first_row['session_count']} oturum / {first_row['guest_count']} kişi)"
    )


def build_daily_summary_report(selected_date):
    day_start_utc, day_end_utc = build_day_range_utc(selected_date)

    started_sessions = get_sessions_started_in_day(day_start_utc, day_end_utc)
    completed_sessions = get_sessions_completed_in_day(day_start_utc, day_end_utc)
    active_sessions = get_active_sessions()
    action_logs = get_action_logs_in_day(day_start_utc, day_end_utc)

    transfer_logs = [
        action_log
        for action_log in action_logs
        if action_log.action_type == "table_transferred"
    ]

    total_guest_count = sum(
        session.party_size or 0
        for session in started_sessions
    )

    average_duration_minutes = calculate_average_duration(completed_sessions)

    area_rows = build_area_summary_rows(started_sessions, completed_sessions)
    table_rows = build_table_summary_rows(started_sessions, completed_sessions)
    staff_rows = build_staff_summary_rows(action_logs)
    transfer_rows = build_transfer_rows(action_logs)
    session_rows = build_session_rows(started_sessions)

    return {
        "selected_date": selected_date,
        "selected_date_value": selected_date.strftime("%Y-%m-%d"),
        "selected_date_display": format_date_for_display(selected_date),
        "summary_cards": [
            {
                "label": "Açılan Oturum",
                "value": len(started_sessions),
                "hint": "Seçilen gün masaya alınan oturum sayısı",
            },
            {
                "label": "Aktif Masa",
                "value": len(active_sessions),
                "hint": "Şu anda devam eden masa oturumları",
            },
            {
                "label": "Boşaltılan Masa",
                "value": len(completed_sessions),
                "hint": "Seçilen gün kapanan oturum sayısı",
            },
            {
                "label": "Toplam Müşteri",
                "value": total_guest_count,
                "hint": "Seçilen gün açılan oturumlardaki kişi toplamı",
            },
            {
                "label": "Transfer",
                "value": len(transfer_logs),
                "hint": "Seçilen gün yapılan masa transferleri",
            },
            {
                "label": "Ortalama Süre",
                "value": format_duration_from_minutes(average_duration_minutes),
                "hint": "Tamamlanan oturumlara göre ortalama süre",
            },
        ],
        "most_used_area": find_most_used_area(area_rows),
        "most_used_table": find_most_used_table(table_rows),
        "area_rows": area_rows,
        "table_rows": table_rows[:10],
        "staff_rows": staff_rows,
        "transfer_rows": transfer_rows,
        "session_rows": session_rows,
    }


@reports_bp.route("/daily-summary", methods=["GET"])
@admin_required
def daily_summary():
    selected_date = parse_selected_date(request.args.get("date"))
    report = build_daily_summary_report(selected_date)

    return render_template(
        "admin/reports/daily_summary.html",
        app_name="Lido Masa Takip Sistemi",
        report=report,
    )