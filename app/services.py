from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.audit import log_action
from app.extensions import db
from app.models import Customer, Reservation, ServiceRequest, Table, TableSession, utc_now


DISPLAY_TIMEZONE = ZoneInfo("Europe/Istanbul")


def ensure_utc_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def normalize_optional_text(value):
    if value is None:
        return None

    cleaned_value = str(value).strip()

    if cleaned_value == "":
        return None

    return cleaned_value


def normalize_phone_number(value):
    cleaned_value = normalize_optional_text(value)

    if cleaned_value is None:
        return None

    digits = "".join(
        character
        for character in cleaned_value
        if character.isdigit()
    )

    if digits.startswith("0090") and len(digits) == 14:
        digits = digits[4:]

    if digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]

    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10:
        return None

    return digits


def parse_reservation_local_datetime(date_value, time_value):
    cleaned_date = normalize_optional_text(date_value)
    cleaned_time = normalize_optional_text(time_value)

    if cleaned_date is None:
        raise ValueError("Rezervasyon tarihi zorunludur.")

    if cleaned_time is None:
        raise ValueError("Rezervasyon saati zorunludur.")

    try:
        parsed_date = datetime.strptime(cleaned_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Rezervasyon tarihi geçerli değil.") from exc

    try:
        parsed_time = datetime.strptime(cleaned_time, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Rezervasyon saati geçerli değil.") from exc

    local_datetime = datetime.combine(parsed_date, parsed_time).replace(
        tzinfo=DISPLAY_TIMEZONE
    )

    return ensure_utc_datetime(local_datetime)


def parse_positive_minutes(value, default_value, field_label):
    cleaned_value = normalize_optional_text(value)

    if cleaned_value is None:
        return default_value

    try:
        parsed_value = int(cleaned_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_label} geçerli bir sayı olmalıdır.") from exc

    if parsed_value < 1:
        raise ValueError(f"{field_label} en az 1 dakika olmalıdır.")

    if parsed_value > 1440:
        raise ValueError(f"{field_label} 1440 dakikadan fazla olamaz.")

    return parsed_value


def parse_deposit_amount_tl(value):
    cleaned_value = normalize_optional_text(value)

    if cleaned_value is None:
        return None

    cleaned_value = (
        cleaned_value
        .replace("TL", "")
        .replace("tl", "")
        .replace("₺", "")
        .replace(" ", "")
        .strip()
    )

    if cleaned_value == "":
        return None

    if "," in cleaned_value and "." in cleaned_value:
        cleaned_value = cleaned_value.replace(".", "").replace(",", ".")
    elif "," in cleaned_value:
        cleaned_value = cleaned_value.replace(",", ".")

    try:
        deposit_amount = Decimal(cleaned_value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Kapora tutarı geçerli bir TL tutarı olmalıdır.") from exc

    if deposit_amount < Decimal("0"):
        raise ValueError("Kapora tutarı negatif olamaz.")

    if deposit_amount > Decimal("999999999.99"):
        raise ValueError("Kapora tutarı çok yüksek görünüyor.")

    return deposit_amount.quantize(Decimal("0.01"))


def normalize_reservation_phone_or_raise(value):
    cleaned_phone = normalize_optional_text(value)

    if cleaned_phone is None:
        raise ValueError("Rezervasyon için telefon zorunludur.")

    phone_normalized = normalize_phone_number(cleaned_phone)

    if phone_normalized is None:
        raise ValueError("Rezervasyon telefonu geçerli değil. Örnek: 05338463131")

    return cleaned_phone, phone_normalized


def parse_table_id(value):
    try:
        table_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Masa bilgisi geçerli değil.") from exc

    if table_id < 1:
        raise ValueError("Masa bilgisi geçerli değil.")

    return table_id


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


def format_reservation_datetime_for_message(value):
    if value is None:
        return "-"

    normalized_value = value

    if normalized_value.tzinfo is None:
        normalized_value = normalized_value.replace(tzinfo=timezone.utc)

    local_value = normalized_value.astimezone(DISPLAY_TIMEZONE)

    return local_value.strftime("%d.%m.%Y %H:%M")


def build_reservation_assignment_block_message(reservation, operation_label="müşteri ataması"):
    table_code = "-"

    if reservation.table is not None:
        table_code = reservation.table.code

    reservation_time_text = format_reservation_datetime_for_message(
        reservation.reservation_at
    )
    customer_name = reservation.customer_name or "İsimsiz müşteri"
    customer_phone = reservation.customer_phone or "-"
    party_size = reservation.party_size or "-"
    protection_minutes = (
        reservation.protection_minutes
        or Reservation.DEFAULT_PROTECTION_MINUTES
    )

    return (
        f"{table_code} masasında {reservation_time_text} rezervasyonu var. "
        f"Rezervasyon koruma süresi ({protection_minutes} dk) başladığı için "
        f"bu masaya {operation_label} yapılamaz. "
        f"Rezervasyon: {customer_name} / {customer_phone} / {party_size} kişi."
    )


def find_or_create_customer_for_assignment(customer_name=None, customer_phone=None):
    cleaned_customer_name = normalize_optional_text(customer_name)
    cleaned_customer_phone = normalize_optional_text(customer_phone)
    phone_normalized = normalize_phone_number(cleaned_customer_phone)

    if phone_normalized is None:
        return None, None, "no_phone_match"

    customer = Customer.query.filter_by(phone_normalized=phone_normalized).first()
    now = utc_now()

    if customer is None:
        customer = Customer(
            full_name=cleaned_customer_name,
            phone_raw=cleaned_customer_phone,
            phone_normalized=phone_normalized,
            first_seen_at=now,
            last_seen_at=now,
            visit_count=0,
            is_active=True,
        )
        db.session.add(customer)
        db.session.flush()
        match_status = "created"
    else:
        if cleaned_customer_name is not None:
            customer.full_name = cleaned_customer_name

        if cleaned_customer_phone is not None:
            customer.phone_raw = cleaned_customer_phone

        if customer.first_seen_at is None:
            customer.first_seen_at = now

        customer.last_seen_at = now
        customer.is_active = True
        match_status = "matched"

    customer.visit_count = (customer.visit_count or 0) + 1
    customer.last_seen_at = now

    return customer, phone_normalized, match_status


def assign_table(
    table_id,
    party_size,
    customer_name=None,
    customer_phone=None,
    note=None,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    parsed_table_id = parse_table_id(table_id)

    table = db.session.get(Table, parsed_table_id)

    if table is None:
        raise ValueError("Seçilen masa bulunamadı.")

    if table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masaya müşteri atanamaz.")

    if table.status != Table.STATUS_EMPTY:
        raise ValueError("Sadece boş masaya müşteri atanabilir.")

    active_session = get_active_session_for_table(table.id)

    if active_session is not None:
        raise ValueError("Bu masa için zaten aktif bir müşteri oturumu var.")

    blocking_reservation = get_blocking_reservation_for_table(table.id)

    if blocking_reservation is not None:
        raise ValueError(
            build_reservation_assignment_block_message(
                blocking_reservation,
                operation_label="müşteri ataması",
            )
        )

    parsed_party_size = parse_party_size(party_size)
    cleaned_customer_name = normalize_optional_text(customer_name)
    cleaned_customer_phone = normalize_optional_text(customer_phone)
    cleaned_note = normalize_optional_text(note)

    customer, phone_normalized, customer_match_status = find_or_create_customer_for_assignment(
        customer_name=cleaned_customer_name,
        customer_phone=cleaned_customer_phone,
    )

    table_session = TableSession(
        table_id=table.id,
        customer_id=customer.id if customer is not None else None,
        customer_name=cleaned_customer_name,
        customer_phone=cleaned_customer_phone,
        note=cleaned_note,
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
            "customer_id": table_session.customer_id,
            "customer_name": table_session.customer_name,
            "customer_phone": table_session.customer_phone,
            "customer_phone_normalized": phone_normalized,
            "customer_match_status": customer_match_status,
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
    username_snapshot="system",
    role_snapshot="system",
):
    parsed_table_id = parse_table_id(table_id)

    table = db.session.get(Table, parsed_table_id)

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

    active_service_requests = ServiceRequest.query.filter(
        ServiceRequest.table_session_id == active_session.id,
        ServiceRequest.status.in_(ACTIVE_SERVICE_REQUEST_STATUSES),
    ).all()

    for service_request in active_service_requests:
        service_request.status = ServiceRequest.STATUS_COMPLETED
        service_request.completed_at = check_out_time
        service_request.completed_by_user_id = user_id

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
            "customer_id": active_session.customer_id,
            "party_size": active_session.party_size,
            "duration_minutes": duration_minutes,
            "completed_service_request_count": len(active_service_requests),
            "customer_name": active_session.customer_name,
            "customer_phone": active_session.customer_phone,
        },
    )

    db.session.commit()

    return active_session


def transfer_table(
    source_table_id,
    target_table_id,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    parsed_source_table_id = parse_table_id(source_table_id)
    parsed_target_table_id = parse_table_id(target_table_id)

    if parsed_source_table_id == parsed_target_table_id:
        raise ValueError("Aynı masaya transfer yapılamaz.")

    source_table = db.session.get(Table, parsed_source_table_id)
    target_table = db.session.get(Table, parsed_target_table_id)

    if source_table is None:
        raise ValueError("Transfer edilecek masa bulunamadı.")

    if target_table is None:
        raise ValueError("Hedef masa bulunamadı.")

    if source_table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masa transfer edilemez.")

    if target_table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masaya transfer yapılamaz.")

    if source_table.status not in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]:
        raise ValueError("Sadece dolu masa transfer edilebilir.")

    if target_table.status != Table.STATUS_EMPTY:
        raise ValueError("Transfer için hedef masa boş olmalıdır.")

    active_session = get_active_session_for_table(source_table.id)

    if active_session is None:
        raise ValueError("Transfer edilecek masada aktif müşteri oturumu bulunamadı.")

    target_active_session = get_active_session_for_table(target_table.id)

    if target_active_session is not None:
        raise ValueError("Hedef masa için zaten aktif müşteri oturumu var.")

    blocking_reservation = get_blocking_reservation_for_table(target_table.id)

    if blocking_reservation is not None:
        raise ValueError(
            build_reservation_assignment_block_message(
                blocking_reservation,
                operation_label="transfer",
            )
        )

    old_table_code = source_table.code
    old_area_name = source_table.area.name
    new_table_code = target_table.code
    new_area_name = target_table.area.name
    transferred_status = source_table.status

    active_session.table_id = target_table.id

    active_service_requests = ServiceRequest.query.filter(
        ServiceRequest.table_session_id == active_session.id,
        ServiceRequest.status.in_(ACTIVE_SERVICE_REQUEST_STATUSES),
    ).all()

    for service_request in active_service_requests:
        service_request.table_id = target_table.id

    source_table.status = Table.STATUS_EMPTY
    target_table.status = transferred_status

    log_action(
        action_type="table_transferred",
        target_type="table",
        target_id=target_table.id,
        target_label=f"{old_table_code} -> {new_table_code}",
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"Müşteri {old_table_code} masasından {new_table_code} masasına transfer edildi."
        ),
        extra_data={
            "old_table_id": source_table.id,
            "old_table_code": old_table_code,
            "old_area_name": old_area_name,
            "new_table_id": target_table.id,
            "new_table_code": new_table_code,
            "new_area_name": new_area_name,
            "table_session_id": active_session.id,
            "customer_id": active_session.customer_id,
            "party_size": active_session.party_size,
            "customer_name": active_session.customer_name,
            "customer_phone": active_session.customer_phone,
            "note": active_session.note,
        },
    )

    db.session.commit()

    return active_session


RESERVATION_STATUS_LABELS = {
    Reservation.STATUS_CONFIRMED: "Onaylandı",
    Reservation.STATUS_SEATED: "Masaya Alındı",
    Reservation.STATUS_COMPLETED: "Tamamlandı",
    Reservation.STATUS_CANCELLED: "İptal",
    Reservation.STATUS_NO_SHOW: "Gelmedi",
}

ACTIVE_RESERVATION_STATUSES = {
    Reservation.STATUS_CONFIRMED,
    Reservation.STATUS_SEATED,
}


def get_reservation_status_label(status):
    return RESERVATION_STATUS_LABELS.get(status, status or "-")


def find_or_create_customer_for_reservation(customer_name=None, customer_phone=None):
    cleaned_customer_name = normalize_optional_text(customer_name)
    cleaned_customer_phone, phone_normalized = normalize_reservation_phone_or_raise(customer_phone)
    customer = Customer.query.filter_by(phone_normalized=phone_normalized).first()
    now = utc_now()

    if customer is None:
        customer = Customer(
            full_name=cleaned_customer_name,
            phone_raw=cleaned_customer_phone,
            phone_normalized=phone_normalized,
            first_seen_at=now,
            last_seen_at=now,
            visit_count=0,
            reservation_count=0,
            no_show_count=0,
            is_active=True,
        )
        db.session.add(customer)
        db.session.flush()
        match_status = "created"
    else:
        if cleaned_customer_name is not None:
            customer.full_name = cleaned_customer_name

        customer.phone_raw = cleaned_customer_phone
        customer.last_seen_at = now
        customer.is_active = True
        match_status = "matched"

    return customer, phone_normalized, match_status


def get_reservation_conflict(table_id, reservation_at, expected_end_at, exclude_reservation_id=None):
    conflict_query = Reservation.query.filter(
        Reservation.table_id == table_id,
        Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
        Reservation.reservation_at < expected_end_at,
        Reservation.expected_end_at > reservation_at,
    )

    if exclude_reservation_id is not None:
        conflict_query = conflict_query.filter(Reservation.id != exclude_reservation_id)

    return conflict_query.order_by(Reservation.reservation_at.asc()).first()


def create_reservation(
    table_id,
    reservation_date,
    reservation_time,
    party_size,
    customer_name=None,
    customer_phone=None,
    deposit_amount_tl=None,
    deposit_note=None,
    note=None,
    duration_minutes=None,
    protection_minutes=None,
    no_show_tolerance_minutes=None,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    parsed_table_id = parse_table_id(table_id)
    table = db.session.get(Table, parsed_table_id)

    if table is None:
        raise ValueError("Rezervasyon yapılacak masa bulunamadı.")

    if table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masaya rezervasyon alınamaz.")

    parsed_party_size = parse_party_size(party_size)
    reservation_at = parse_reservation_local_datetime(reservation_date, reservation_time)

    if reservation_at <= ensure_utc_datetime(utc_now()):
        raise ValueError("Rezervasyon tarihi ve saati ileri bir zaman olmalıdır.")

    parsed_duration_minutes = parse_positive_minutes(
        duration_minutes,
        Reservation.DEFAULT_DURATION_MINUTES,
        "Rezervasyon süresi",
    )
    parsed_protection_minutes = parse_positive_minutes(
        protection_minutes,
        Reservation.DEFAULT_PROTECTION_MINUTES,
        "Hazırlık / koruma süresi",
    )
    parsed_no_show_tolerance_minutes = parse_positive_minutes(
        no_show_tolerance_minutes,
        Reservation.DEFAULT_NO_SHOW_TOLERANCE_MINUTES,
        "Geç kalma toleransı",
    )
    expected_end_at = reservation_at + timedelta(minutes=parsed_duration_minutes)

    conflict_reservation = get_reservation_conflict(
        table_id=table.id,
        reservation_at=reservation_at,
        expected_end_at=expected_end_at,
    )

    if conflict_reservation is not None:
        raise ValueError(
            f"{table.code} masasında bu saat aralığıyla çakışan başka bir rezervasyon var."
        )

    cleaned_customer_name = normalize_optional_text(customer_name)
    cleaned_deposit_note = normalize_optional_text(deposit_note)
    cleaned_note = normalize_optional_text(note)
    parsed_deposit_amount_tl = parse_deposit_amount_tl(deposit_amount_tl)

    customer, phone_normalized, customer_match_status = find_or_create_customer_for_reservation(
        customer_name=cleaned_customer_name,
        customer_phone=customer_phone,
    )

    customer.reservation_count = (customer.reservation_count or 0) + 1

    reservation = Reservation(
        table_id=table.id,
        customer_id=customer.id,
        customer_name=cleaned_customer_name,
        customer_phone=normalize_optional_text(customer_phone),
        customer_phone_normalized=phone_normalized,
        party_size=parsed_party_size,
        reservation_at=reservation_at,
        expected_end_at=expected_end_at,
        duration_minutes=parsed_duration_minutes,
        protection_minutes=parsed_protection_minutes,
        no_show_tolerance_minutes=parsed_no_show_tolerance_minutes,
        deposit_amount_tl=parsed_deposit_amount_tl,
        deposit_note=cleaned_deposit_note,
        note=cleaned_note,
        status=Reservation.STATUS_CONFIRMED,
        created_by_user_id=user_id,
    )

    db.session.add(reservation)
    db.session.flush()

    log_action(
        action_type="reservation_created",
        target_type="reservation",
        target_id=reservation.id,
        target_label=f"{table.code} - {reservation_at.isoformat()}",
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{table.code} masasına {parsed_party_size} kişilik rezervasyon alındı."
        ),
        extra_data={
            "reservation_id": reservation.id,
            "table_id": table.id,
            "table_code": table.code,
            "area_name": table.area.name if table.area else None,
            "customer_id": customer.id,
            "customer_name": reservation.customer_name,
            "customer_phone": reservation.customer_phone,
            "customer_phone_normalized": phone_normalized,
            "customer_match_status": customer_match_status,
            "party_size": parsed_party_size,
            "reservation_at": reservation.reservation_at.isoformat(),
            "expected_end_at": reservation.expected_end_at.isoformat(),
            "duration_minutes": parsed_duration_minutes,
            "protection_minutes": parsed_protection_minutes,
            "no_show_tolerance_minutes": parsed_no_show_tolerance_minutes,
            "deposit_amount_tl": str(parsed_deposit_amount_tl) if parsed_deposit_amount_tl is not None else None,
            "deposit_note": reservation.deposit_note,
            "note": reservation.note,
        },
    )

    db.session.commit()

    return reservation


def update_reservation(
    reservation_id,
    table_id,
    reservation_date,
    reservation_time,
    party_size,
    customer_name=None,
    customer_phone=None,
    deposit_amount_tl=None,
    deposit_note=None,
    note=None,
    duration_minutes=None,
    protection_minutes=None,
    no_show_tolerance_minutes=None,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    reservation = db.session.get(Reservation, reservation_id)

    if reservation is None:
        raise ValueError("Rezervasyon bulunamadı.")

    if reservation.status != Reservation.STATUS_CONFIRMED:
        raise ValueError("Sadece onaylı rezervasyonlar düzenlenebilir.")

    parsed_table_id = parse_table_id(table_id)
    table = db.session.get(Table, parsed_table_id)

    if table is None:
        raise ValueError("Rezervasyonun atanacağı masa bulunamadı.")

    if table.status == Table.STATUS_INACTIVE:
        raise ValueError("Pasif durumdaki masaya rezervasyon taşınamaz.")

    parsed_party_size = parse_party_size(party_size)
    reservation_at = parse_reservation_local_datetime(reservation_date, reservation_time)

    if reservation_at <= ensure_utc_datetime(utc_now()):
        raise ValueError("Rezervasyon tarihi ve saati ileri bir zaman olmalıdır.")

    parsed_duration_minutes = parse_positive_minutes(
        duration_minutes,
        reservation.duration_minutes or Reservation.DEFAULT_DURATION_MINUTES,
        "Rezervasyon süresi",
    )
    parsed_protection_minutes = parse_positive_minutes(
        protection_minutes,
        reservation.protection_minutes or Reservation.DEFAULT_PROTECTION_MINUTES,
        "Hazırlık / koruma süresi",
    )
    parsed_no_show_tolerance_minutes = parse_positive_minutes(
        no_show_tolerance_minutes,
        reservation.no_show_tolerance_minutes or Reservation.DEFAULT_NO_SHOW_TOLERANCE_MINUTES,
        "Geç kalma toleransı",
    )
    expected_end_at = reservation_at + timedelta(minutes=parsed_duration_minutes)

    conflict_reservation = get_reservation_conflict(
        table_id=table.id,
        reservation_at=reservation_at,
        expected_end_at=expected_end_at,
        exclude_reservation_id=reservation.id,
    )

    if conflict_reservation is not None:
        raise ValueError(
            f"{table.code} masasında bu saat aralığıyla çakışan başka bir rezervasyon var."
        )

    cleaned_customer_name = normalize_optional_text(customer_name)
    cleaned_customer_phone = normalize_optional_text(customer_phone)
    cleaned_deposit_note = normalize_optional_text(deposit_note)
    cleaned_note = normalize_optional_text(note)
    parsed_deposit_amount_tl = parse_deposit_amount_tl(deposit_amount_tl)

    old_table = reservation.table
    old_customer = reservation.customer
    old_customer_id = reservation.customer_id
    old_snapshot = {
        "table_id": reservation.table_id,
        "table_code": old_table.code if old_table is not None else None,
        "customer_id": reservation.customer_id,
        "customer_name": reservation.customer_name,
        "customer_phone": reservation.customer_phone,
        "party_size": reservation.party_size,
        "reservation_at": reservation.reservation_at.isoformat() if reservation.reservation_at else None,
        "expected_end_at": reservation.expected_end_at.isoformat() if reservation.expected_end_at else None,
        "duration_minutes": reservation.duration_minutes,
        "protection_minutes": reservation.protection_minutes,
        "no_show_tolerance_minutes": reservation.no_show_tolerance_minutes,
        "deposit_amount_tl": str(reservation.deposit_amount_tl) if reservation.deposit_amount_tl is not None else None,
        "deposit_note": reservation.deposit_note,
        "note": reservation.note,
    }

    customer, phone_normalized, customer_match_status = find_or_create_customer_for_reservation(
        customer_name=cleaned_customer_name,
        customer_phone=cleaned_customer_phone,
    )

    if old_customer_id != customer.id:
        if old_customer is not None:
            old_customer.reservation_count = max((old_customer.reservation_count or 0) - 1, 0)

        customer.reservation_count = (customer.reservation_count or 0) + 1

    reservation.table_id = table.id
    reservation.customer_id = customer.id
    reservation.customer_name = cleaned_customer_name
    reservation.customer_phone = cleaned_customer_phone
    reservation.customer_phone_normalized = phone_normalized
    reservation.party_size = parsed_party_size
    reservation.reservation_at = reservation_at
    reservation.expected_end_at = expected_end_at
    reservation.duration_minutes = parsed_duration_minutes
    reservation.protection_minutes = parsed_protection_minutes
    reservation.no_show_tolerance_minutes = parsed_no_show_tolerance_minutes
    reservation.deposit_amount_tl = parsed_deposit_amount_tl
    reservation.deposit_note = cleaned_deposit_note
    reservation.note = cleaned_note
    reservation.updated_by_user_id = user_id

    db.session.flush()

    log_action(
        action_type="reservation_updated",
        target_type="reservation",
        target_id=reservation.id,
        target_label=f"{table.code} - {reservation_at.isoformat()}",
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{table.code} masasına ait rezervasyon güncellendi."
        ),
        extra_data={
            "reservation_id": reservation.id,
            "old": old_snapshot,
            "new": {
                "table_id": table.id,
                "table_code": table.code,
                "area_name": table.area.name if table.area else None,
                "customer_id": customer.id,
                "customer_name": reservation.customer_name,
                "customer_phone": reservation.customer_phone,
                "customer_phone_normalized": phone_normalized,
                "customer_match_status": customer_match_status,
                "party_size": parsed_party_size,
                "reservation_at": reservation.reservation_at.isoformat(),
                "expected_end_at": reservation.expected_end_at.isoformat(),
                "duration_minutes": parsed_duration_minutes,
                "protection_minutes": parsed_protection_minutes,
                "no_show_tolerance_minutes": parsed_no_show_tolerance_minutes,
                "deposit_amount_tl": str(parsed_deposit_amount_tl) if parsed_deposit_amount_tl is not None else None,
                "deposit_note": reservation.deposit_note,
                "note": reservation.note,
            },
        },
    )

    db.session.commit()

    return reservation


def get_reservation_protection_start(reservation):
    reservation_at = ensure_utc_datetime(reservation.reservation_at)
    return reservation_at - timedelta(minutes=reservation.protection_minutes or 0)


def get_reservation_no_show_deadline(reservation):
    reservation_at = ensure_utc_datetime(reservation.reservation_at)
    return reservation_at + timedelta(minutes=reservation.no_show_tolerance_minutes or 0)


def get_blocking_reservation_for_table(table_id, reference_time=None):
    if reference_time is None:
        reference_time = utc_now()

    reference_time = ensure_utc_datetime(reference_time)

    confirmed_reservations = (
        Reservation.query
        .filter(
            Reservation.table_id == table_id,
            Reservation.status == Reservation.STATUS_CONFIRMED,
            Reservation.reservation_at >= reference_time - timedelta(hours=6),
        )
        .order_by(Reservation.reservation_at.asc())
        .all()
    )

    for reservation in confirmed_reservations:
        protection_start = get_reservation_protection_start(reservation)
        no_show_deadline = get_reservation_no_show_deadline(reservation)

        if protection_start <= reference_time <= no_show_deadline:
            return reservation

    return None


def mark_reservation_no_show(
    reservation_id,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    reservation = db.session.get(Reservation, reservation_id)

    if reservation is None:
        raise ValueError("Rezervasyon bulunamadı.")

    if reservation.status == Reservation.STATUS_NO_SHOW:
        return reservation

    if reservation.status in [Reservation.STATUS_CANCELLED, Reservation.STATUS_COMPLETED]:
        raise ValueError("Bu rezervasyon gelmedi olarak işaretlenemez.")

    now = utc_now()
    reservation.status = Reservation.STATUS_NO_SHOW
    reservation.no_show_at = now
    reservation.no_show_by_user_id = user_id

    if reservation.customer is not None:
        reservation.customer.no_show_count = (reservation.customer.no_show_count or 0) + 1
        reservation.customer.last_no_show_at = now
        reservation.customer.last_seen_at = now

    log_action(
        action_type="reservation_no_show",
        target_type="reservation",
        target_id=reservation.id,
        target_label=reservation.table.code if reservation.table else str(reservation.id),
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{reservation.table.code if reservation.table else '-'} masası rezervasyonu gelmedi olarak işaretlendi."
        ),
        extra_data={
            "reservation_id": reservation.id,
            "table_id": reservation.table_id,
            "table_code": reservation.table.code if reservation.table else None,
            "customer_id": reservation.customer_id,
            "customer_name": reservation.customer_name,
            "customer_phone": reservation.customer_phone,
            "reservation_at": reservation.reservation_at.isoformat() if reservation.reservation_at else None,
            "no_show_at": now.isoformat(),
        },
    )

    db.session.commit()

    return reservation


def cancel_reservation(
    reservation_id,
    cancel_reason=None,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    reservation = db.session.get(Reservation, reservation_id)

    if reservation is None:
        raise ValueError("Rezervasyon bulunamadı.")

    if reservation.status == Reservation.STATUS_CANCELLED:
        return reservation

    if reservation.status in [Reservation.STATUS_SEATED, Reservation.STATUS_COMPLETED]:
        raise ValueError("Masaya alınmış veya tamamlanmış rezervasyon iptal edilemez.")

    if reservation.status == Reservation.STATUS_NO_SHOW:
        raise ValueError("Gelmedi olarak işaretlenmiş rezervasyon iptal edilemez.")

    cleaned_cancel_reason = normalize_optional_text(cancel_reason)
    now = utc_now()

    reservation.status = Reservation.STATUS_CANCELLED
    reservation.cancelled_at = now
    reservation.cancelled_by_user_id = user_id
    reservation.cancel_reason = cleaned_cancel_reason

    log_action(
        action_type="reservation_cancelled",
        target_type="reservation",
        target_id=reservation.id,
        target_label=reservation.table.code if reservation.table else str(reservation.id),
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{reservation.table.code if reservation.table else '-'} masası rezervasyonu iptal edildi."
        ),
        extra_data={
            "reservation_id": reservation.id,
            "table_id": reservation.table_id,
            "table_code": reservation.table.code if reservation.table else None,
            "customer_id": reservation.customer_id,
            "customer_name": reservation.customer_name,
            "customer_phone": reservation.customer_phone,
            "reservation_at": reservation.reservation_at.isoformat() if reservation.reservation_at else None,
            "cancelled_at": now.isoformat(),
            "cancel_reason": cleaned_cancel_reason,
        },
    )

    db.session.commit()

    return reservation


SERVICE_REQUEST_TYPE_LABELS = {
    ServiceRequest.TYPE_WAITER: "Garson Çağır",
    ServiceRequest.TYPE_MENU: "Menü İste",
    ServiceRequest.TYPE_BILL: "Hesap İste",
    ServiceRequest.TYPE_CLEANING: "Temizlik / Kül Tablası",
    ServiceRequest.TYPE_OTHER: "Diğer Not",
}

SERVICE_REQUEST_STATUS_LABELS = {
    ServiceRequest.STATUS_OPEN: "Bekliyor",
    ServiceRequest.STATUS_SEEN: "Görüldü",
    ServiceRequest.STATUS_COMPLETED: "Tamamlandı",
    ServiceRequest.STATUS_CANCELLED: "İptal",
}

ACTIVE_SERVICE_REQUEST_STATUSES = {
    ServiceRequest.STATUS_OPEN,
    ServiceRequest.STATUS_SEEN,
}


def get_service_request_type_label(request_type):
    return SERVICE_REQUEST_TYPE_LABELS.get(request_type, request_type or "-")


def get_service_request_status_label(status):
    return SERVICE_REQUEST_STATUS_LABELS.get(status, status or "-")


def get_active_service_request_for_table_and_type(table_id, table_session_id, request_type):
    query = ServiceRequest.query.filter(
        ServiceRequest.table_id == table_id,
        ServiceRequest.request_type == request_type,
        ServiceRequest.status.in_(ACTIVE_SERVICE_REQUEST_STATUSES),
    )

    if table_session_id is None:
        query = query.filter(ServiceRequest.table_session_id.is_(None))
    else:
        query = query.filter(ServiceRequest.table_session_id == table_session_id)

    return query.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc()).first()


def create_service_request_from_qr(qr_token, request_type, note=None):
    cleaned_qr_token = normalize_optional_text(qr_token)
    cleaned_request_type = normalize_optional_text(request_type)
    cleaned_note = normalize_optional_text(note)

    if cleaned_qr_token is None:
        raise ValueError("QR bağlantısı geçerli değil.")

    table = Table.query.filter_by(qr_token=cleaned_qr_token).first()

    if table is None:
        raise ValueError("Bu QR kod sisteme kayıtlı bir masaya ait değil.")

    if table.status == Table.STATUS_INACTIVE:
        raise ValueError("Bu masa pasif durumda olduğu için çağrı oluşturulamaz.")

    if cleaned_request_type not in SERVICE_REQUEST_TYPE_LABELS:
        raise ValueError("Geçerli bir çağrı tipi seçmelisiniz.")

    active_session = get_active_session_for_table(table.id)

    if active_session is None:
        raise ValueError("Bu masa için aktif müşteri oturumu bulunmuyor.")

    existing_request = get_active_service_request_for_table_and_type(
        table_id=table.id,
        table_session_id=active_session.id,
        request_type=cleaned_request_type,
    )

    if existing_request is not None:
        return existing_request, False

    service_request = ServiceRequest(
        table_id=table.id,
        table_session_id=active_session.id,
        request_type=cleaned_request_type,
        note=cleaned_note,
        status=ServiceRequest.STATUS_OPEN,
    )

    db.session.add(service_request)
    db.session.flush()

    log_action(
        action_type="service_request_created",
        target_type="table",
        target_id=table.id,
        target_label=table.code,
        username_snapshot="qr_customer",
        role_snapshot="customer",
        description=(
            f"{table.code} masasından {get_service_request_type_label(cleaned_request_type)} çağrısı oluşturuldu."
        ),
        extra_data={
            "service_request_id": service_request.id,
            "table_id": table.id,
            "table_code": table.code,
            "area_name": table.area.name if table.area else None,
            "table_session_id": active_session.id,
            "request_type": service_request.request_type,
            "request_type_label": get_service_request_type_label(service_request.request_type),
            "note": service_request.note,
        },
    )

    db.session.commit()

    return service_request, True


def get_active_service_requests():
    return (
        ServiceRequest.query
        .join(Table, ServiceRequest.table_id == Table.id)
        .filter(ServiceRequest.status.in_(ACTIVE_SERVICE_REQUEST_STATUSES))
        .order_by(ServiceRequest.created_at.asc(), ServiceRequest.id.asc())
        .all()
    )


def build_service_request_api_row(service_request):
    table = service_request.table
    area_name = "-"
    table_code = "-"

    if table is not None:
        table_code = table.code
        if table.area is not None:
            area_name = table.area.name

    created_at = service_request.created_at

    elapsed_minutes = 0
    if created_at is not None:
        normalized_created_at = created_at
        if normalized_created_at.tzinfo is None:
            normalized_created_at = normalized_created_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = (utc_now() - normalized_created_at).total_seconds()
        elapsed_minutes = max(0, int(elapsed_seconds // 60))

    return {
        "id": service_request.id,
        "table_id": service_request.table_id,
        "table_code": table_code,
        "area_name": area_name,
        "request_type": service_request.request_type,
        "request_type_label": get_service_request_type_label(service_request.request_type),
        "status": service_request.status,
        "status_label": get_service_request_status_label(service_request.status),
        "note": service_request.note or "",
        "elapsed_minutes": elapsed_minutes,
        "elapsed_text": f"{elapsed_minutes} dk önce" if elapsed_minutes > 0 else "Az önce",
    }


def mark_service_request_seen(
    service_request_id,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    service_request = db.session.get(ServiceRequest, service_request_id)

    if service_request is None:
        raise ValueError("Servis çağrısı bulunamadı.")

    if service_request.status == ServiceRequest.STATUS_COMPLETED:
        raise ValueError("Tamamlanmış çağrı tekrar görüldü yapılamaz.")

    if service_request.status == ServiceRequest.STATUS_CANCELLED:
        raise ValueError("İptal edilmiş çağrı tekrar görüldü yapılamaz.")

    if service_request.status == ServiceRequest.STATUS_OPEN:
        service_request.status = ServiceRequest.STATUS_SEEN
        service_request.seen_at = utc_now()
        service_request.seen_by_user_id = user_id

        log_action(
            action_type="service_request_seen",
            target_type="service_request",
            target_id=service_request.id,
            target_label=service_request.table.code if service_request.table else str(service_request.id),
            user_id=user_id,
            username_snapshot=username_snapshot,
            role_snapshot=role_snapshot,
            description=(
                f"{service_request.table.code if service_request.table else '-'} masası çağrısı görüldü."
            ),
            extra_data={
                "service_request_id": service_request.id,
                "table_id": service_request.table_id,
                "table_code": service_request.table.code if service_request.table else None,
                "request_type": service_request.request_type,
                "request_type_label": get_service_request_type_label(service_request.request_type),
            },
        )

        db.session.commit()

    return service_request


def complete_service_request(
    service_request_id,
    user_id=None,
    username_snapshot="system",
    role_snapshot="system",
):
    service_request = db.session.get(ServiceRequest, service_request_id)

    if service_request is None:
        raise ValueError("Servis çağrısı bulunamadı.")

    if service_request.status == ServiceRequest.STATUS_COMPLETED:
        return service_request

    if service_request.status == ServiceRequest.STATUS_CANCELLED:
        raise ValueError("İptal edilmiş çağrı tamamlandı yapılamaz.")

    now = utc_now()

    if service_request.status == ServiceRequest.STATUS_OPEN:
        service_request.seen_at = now
        service_request.seen_by_user_id = user_id

    service_request.status = ServiceRequest.STATUS_COMPLETED
    service_request.completed_at = now
    service_request.completed_by_user_id = user_id

    log_action(
        action_type="service_request_completed",
        target_type="service_request",
        target_id=service_request.id,
        target_label=service_request.table.code if service_request.table else str(service_request.id),
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        description=(
            f"{service_request.table.code if service_request.table else '-'} masası çağrısı tamamlandı."
        ),
        extra_data={
            "service_request_id": service_request.id,
            "table_id": service_request.table_id,
            "table_code": service_request.table.code if service_request.table else None,
            "request_type": service_request.request_type,
            "request_type_label": get_service_request_type_label(service_request.request_type),
        },
    )

    db.session.commit()

    return service_request
