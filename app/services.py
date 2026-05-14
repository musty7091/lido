from datetime import timezone

from app.audit import log_action
from app.extensions import db
from app.models import Table, TableSession, utc_now


def normalize_optional_text(value):
    if value is None:
        return None

    cleaned_value = str(value).strip()

    if cleaned_value == "":
        return None

    return cleaned_value


def parse_party_size(value):
    try:
        party_size = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Kişi sayısı geçerli bir sayı olmalıdır.") from exc

    if party_size < 1:
        raise ValueError("Kişi sayısı en az 1 olmalıdır.")

    if party_size > 50:
        raise ValueError("Kişi sayısı 50 kişiden fazla olamaz.")

    return party_size


def get_active_session_for_table(table_id):
    return (
        TableSession.query.filter_by(
            table_id=table_id,
            status=TableSession.STATUS_ACTIVE,
        )
        .order_by(TableSession.check_in_at.desc())
        .first()
    )


def assign_table(
    table_id,
    party_size,
    customer_name=None,
    customer_phone=None,
    note=None,
    user_id=None,
    username_snapshot="demo_user",
    role_snapshot="demo_operator",
):
    table = Table.query.get(table_id)

    if table is None:
        raise ValueError("Seçilen masa bulunamadı.")

    if table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masaya müşteri atanamaz.")

    if table.status != Table.STATUS_EMPTY:
        raise ValueError("Sadece boş masaya müşteri atanabilir.")

    active_session = get_active_session_for_table(table.id)

    if active_session is not None:
        raise ValueError("Bu masa için zaten aktif bir müşteri oturumu var.")

    parsed_party_size = parse_party_size(party_size)

    table_session = TableSession(
        table_id=table.id,
        customer_name=normalize_optional_text(customer_name),
        customer_phone=normalize_optional_text(customer_phone),
        note=normalize_optional_text(note),
        party_size=parsed_party_size,
        status=TableSession.STATUS_ACTIVE,
        opened_by_user_id=user_id,
    )

    table.status = Table.STATUS_OCCUPIED

    db.session.add(table_session)
    db.session.flush()

    log_action(
        action_type="table_assigned",
        target_type="table",
        target_id=table.id,
        target_label=table.code,
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{table.code} masasına {parsed_party_size} kişi yönlendirildi."
        ),
        extra_data={
            "table_code": table.code,
            "area_name": table.area.name,
            "party_size": parsed_party_size,
            "customer_name": table_session.customer_name,
            "customer_phone": table_session.customer_phone,
            "note": table_session.note,
            "table_session_id": table_session.id,
        },
    )

    db.session.commit()

    return table_session


def calculate_duration_minutes(start_time, end_time):
    normalized_start_time = start_time

    if normalized_start_time.tzinfo is None:
        normalized_start_time = normalized_start_time.replace(tzinfo=timezone.utc)

    duration_seconds = (end_time - normalized_start_time).total_seconds()
    duration_minutes = int(duration_seconds // 60)

    if duration_minutes < 0:
        return 0

    return duration_minutes


def clear_table(
    table_id,
    user_id=None,
    username_snapshot="demo_user",
    role_snapshot="demo_operator",
):
    table = Table.query.get(table_id)

    if table is None:
        raise ValueError("Seçilen masa bulunamadı.")

    if table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masa boşaltılamaz.")

    if table.status not in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]:
        raise ValueError("Sadece dolu masa boşaltılabilir.")

    active_session = get_active_session_for_table(table.id)

    if active_session is None:
        raise ValueError("Bu masa için aktif müşteri oturumu bulunamadı.")

    check_out_time = utc_now()
    duration_minutes = calculate_duration_minutes(
        active_session.check_in_at,
        check_out_time,
    )

    active_session.check_out_at = check_out_time
    active_session.duration_minutes = duration_minutes
    active_session.status = TableSession.STATUS_COMPLETED
    active_session.closed_by_user_id = user_id

    table.status = Table.STATUS_EMPTY

    log_action(
        action_type="table_cleared",
        target_type="table",
        target_id=table.id,
        target_label=table.code,
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{table.code} masası boşaltıldı. Kalış süresi: {duration_minutes} dakika."
        ),
        extra_data={
            "table_code": table.code,
            "area_name": table.area.name,
            "table_session_id": active_session.id,
            "party_size": active_session.party_size,
            "duration_minutes": duration_minutes,
            "customer_name": active_session.customer_name,
            "customer_phone": active_session.customer_phone,
        },
    )

    db.session.commit()

    return active_session