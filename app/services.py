from datetime import timezone

from app.audit import log_action
from app.extensions import db
from app.models import Customer, ServiceRequest, Table, TableSession, utc_now


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
