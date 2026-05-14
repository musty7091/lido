from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import log_action
from app.extensions import db
from app.models import ActionLog, Area, Table, TableSession, User
from app.permissions import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

DISPLAY_TIMEZONE = ZoneInfo("Europe/Istanbul")


ROLE_CHOICES = [
    {
        "value": User.ROLE_ADMIN,
        "label": "Yönetici",
    },
    {
        "value": User.ROLE_DOOR_STAFF,
        "label": "Kapı Personeli",
    },
    {
        "value": User.ROLE_BAR_STAFF,
        "label": "Bar Personeli",
    },
]


TABLE_STATUS_CHOICES = [
    {
        "value": Table.STATUS_EMPTY,
        "label": "Aktif / Boş",
    },
    {
        "value": Table.STATUS_INACTIVE,
        "label": "Pasif",
    },
]


ACTION_TYPE_LABELS = {
    "database_seed": "Veritabanı Hazırlama",
    "login_success": "Giriş Başarılı",
    "login_failed": "Giriş Başarısız",
    "login_blocked": "Giriş Engellendi",
    "logout": "Çıkış",
    "password_changed": "Şifre Değiştirildi",
    "user_created": "Kullanıcı Oluşturuldu",
    "user_updated": "Kullanıcı Güncellendi",
    "user_role_changed": "Kullanıcı Rolü Değiştirildi",
    "user_activated": "Kullanıcı Aktif Edildi",
    "user_deactivated": "Kullanıcı Pasifleştirildi",
    "user_password_reset": "Kullanıcı Şifresi Sıfırlandı",
    "area_created": "Alan Oluşturuldu",
    "area_updated": "Alan Güncellendi",
    "area_activated": "Alan Aktif Edildi",
    "area_deactivated": "Alan Pasifleştirildi",
    "area_deleted": "Alan Silindi",
    "table_assigned": "Masa Atandı",
    "table_cleared": "Masa Boşaltıldı",
    "table_transferred": "Masa Transferi",
    "table_created": "Masa Oluşturuldu",
    "table_capacity_updated": "Masa Kapasitesi Güncellendi",
    "table_activated": "Masa Aktif Edildi",
    "table_deactivated": "Masa Pasifleştirildi",
}


ROLE_LABELS = {
    User.ROLE_ADMIN: "Yönetici",
    User.ROLE_DOOR_STAFF: "Kapı Personeli",
    User.ROLE_BAR_STAFF: "Bar Personeli",
    "system": "Sistem",
}


TABLE_STATUS_LABELS = {
    Table.STATUS_EMPTY: "Boş",
    Table.STATUS_OCCUPIED: "Dolu",
    Table.STATUS_LONG: "Uzun Süreli",
    Table.STATUS_INACTIVE: "Pasif",
}


TURKISH_SLUG_MAP = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_table_code(value):
    return clean_text(value).upper()


def normalize_prefix(value):
    return clean_text(value).upper()


def slugify(value):
    cleaned_value = clean_text(value).translate(TURKISH_SLUG_MAP).lower()

    slug_chars = []
    previous_dash = False

    for char in cleaned_value:
        if char.isalnum():
            slug_chars.append(char)
            previous_dash = False
        else:
            if not previous_dash:
                slug_chars.append("-")
                previous_dash = True

    slug = "".join(slug_chars).strip("-")

    return slug


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

    return local_value.strftime("%d.%m.%Y %H:%M:%S")


def get_action_type_label(action_type):
    return ACTION_TYPE_LABELS.get(action_type, action_type)


def get_role_label(role):
    return ROLE_LABELS.get(role, role or "-")


def get_table_status_label(status):
    return TABLE_STATUS_LABELS.get(status, status or "-")


def get_role_choices_values():
    return [role_choice["value"] for role_choice in ROLE_CHOICES]


def get_user_or_redirect(user_id):
    user = db.session.get(User, user_id)

    if user is None:
        flash("Kullanıcı bulunamadı.", "danger")
        return None

    return user


def get_area_or_redirect(area_id):
    area = db.session.get(Area, area_id)

    if area is None:
        flash("Alan bulunamadı.", "danger")
        return None

    return area


def get_table_or_redirect(table_id):
    table = db.session.get(Table, table_id)

    if table is None:
        flash("Masa bulunamadı.", "danger")
        return None

    return table


def count_active_admin_users():
    return User.query.filter_by(
        role=User.ROLE_ADMIN,
        is_active=True,
    ).count()


def is_last_active_admin(user):
    if user.role != User.ROLE_ADMIN:
        return False

    if not user.is_active:
        return False

    return count_active_admin_users() <= 1


def count_tables_for_area(area_id):
    return Table.query.filter_by(area_id=area_id).count()


def count_busy_tables_for_area(area_id):
    return Table.query.filter(
        Table.area_id == area_id,
        Table.status.in_([Table.STATUS_OCCUPIED, Table.STATUS_LONG]),
    ).count()


def count_table_sessions_for_area(area_id):
    return (
        TableSession.query
        .join(Table, TableSession.table_id == Table.id)
        .filter(Table.area_id == area_id)
        .count()
    )


def build_action_log_view_model(action_log):
    return {
        "id": action_log.id,
        "created_at": format_datetime_for_display(action_log.created_at),
        "username": action_log.username_snapshot or "Sistem",
        "role": get_role_label(action_log.role_snapshot),
        "action_type": action_log.action_type,
        "action_label": get_action_type_label(action_log.action_type),
        "target_type": action_log.target_type or "-",
        "target_label": action_log.target_label or "-",
        "description": action_log.description,
        "ip_address": action_log.ip_address or "-",
    }


def build_table_view_model(table):
    return {
        "id": table.id,
        "code": table.code,
        "area_name": table.area.name,
        "area_slug": table.area.slug,
        "capacity": table.capacity,
        "status": table.status,
        "status_label": get_table_status_label(table.status),
        "number": table.number,
        "sort_order": table.sort_order,
        "is_busy": table.status in [Table.STATUS_OCCUPIED, Table.STATUS_LONG],
    }


def build_area_summary_view_model(area):
    total_table_count = Table.query.filter_by(area_id=area.id).count()

    active_table_count = Table.query.filter(
        Table.area_id == area.id,
        Table.status != Table.STATUS_INACTIVE,
    ).count()

    inactive_table_count = Table.query.filter_by(
        area_id=area.id,
        status=Table.STATUS_INACTIVE,
    ).count()

    occupied_table_count = count_busy_tables_for_area(area.id)
    session_count = count_table_sessions_for_area(area.id)

    return {
        "id": area.id,
        "name": area.name,
        "slug": area.slug,
        "prefix": area.prefix,
        "display_order": area.display_order,
        "is_active": area.is_active,
        "table_count": total_table_count,
        "active_table_count": active_table_count,
        "inactive_table_count": inactive_table_count,
        "occupied_table_count": occupied_table_count,
        "session_count": session_count,
        "can_delete": occupied_table_count == 0 and session_count == 0,
        "can_change_prefix": total_table_count == 0,
    }


def parse_capacity(value):
    try:
        capacity = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Kapasite geçerli bir sayı olmalıdır.") from exc

    if capacity < 1:
        raise ValueError("Kapasite en az 1 olmalıdır.")

    if capacity > 50:
        raise ValueError("Kapasite 50 kişiden fazla olamaz.")

    return capacity


def parse_display_order(value):
    try:
        display_order = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Sıralama geçerli bir sayı olmalıdır.") from exc

    if display_order < 1:
        raise ValueError("Sıralama en az 1 olmalıdır.")

    if display_order > 999:
        raise ValueError("Sıralama 999 değerinden büyük olamaz.")

    return display_order


def parse_initial_table_count(value):
    try:
        table_count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Başlangıç masa adedi geçerli bir sayı olmalıdır.") from exc

    if table_count < 0:
        raise ValueError("Başlangıç masa adedi negatif olamaz.")

    if table_count > 500:
        raise ValueError("Tek seferde 500 masadan fazla oluşturulamaz.")

    return table_count


def parse_table_number_from_code(area, table_code):
    if not table_code:
        raise ValueError("Masa kodu zorunludur.")

    if " " in table_code:
        raise ValueError("Masa kodunda boşluk olamaz.")

    if not table_code.startswith(area.prefix):
        raise ValueError(
            f"Masa kodu {area.prefix} harfi ile başlamalıdır. Örnek: {area.prefix}101"
        )

    number_part = table_code[len(area.prefix):]

    if not number_part:
        raise ValueError("Masa kodunda sayı bölümü bulunmalıdır.")

    if not number_part.isdigit():
        raise ValueError("Masa kodunun harften sonraki bölümü sayı olmalıdır.")

    table_number = int(number_part)

    if table_number < 1:
        raise ValueError("Masa numarası 1 veya daha büyük olmalıdır.")

    return table_number


def validate_area_create_form(name, prefix, display_order, initial_table_count, default_capacity):
    if not name:
        return "Alan adı zorunludur."

    if len(name) < 2:
        return "Alan adı en az 2 karakter olmalıdır."

    if not prefix:
        return "Prefix zorunludur."

    if len(prefix) > 5:
        return "Prefix en fazla 5 karakter olabilir."

    if not prefix.isalnum():
        return "Prefix sadece harf ve rakamlardan oluşmalıdır."

    area_slug = slugify(name)

    if not area_slug:
        return "Alan adı geçerli bir kısa ad üretmelidir."

    try:
        parse_display_order(display_order)
        parse_initial_table_count(initial_table_count)
        parse_capacity(default_capacity)
    except ValueError as exc:
        return str(exc)

    existing_name = Area.query.filter_by(name=name).first()

    if existing_name is not None:
        return "Bu alan adı zaten kullanılıyor."

    existing_slug = Area.query.filter_by(slug=area_slug).first()

    if existing_slug is not None:
        return "Bu alan için oluşan kısa ad zaten kullanılıyor."

    existing_prefix = Area.query.filter_by(prefix=prefix).first()

    if existing_prefix is not None:
        return "Bu prefix başka bir alanda kullanılıyor."

    return None


def validate_area_update_form(area, name, prefix, display_order, is_active):
    if not name:
        return "Alan adı zorunludur."

    if len(name) < 2:
        return "Alan adı en az 2 karakter olmalıdır."

    if not prefix:
        return "Prefix zorunludur."

    if len(prefix) > 5:
        return "Prefix en fazla 5 karakter olabilir."

    if not prefix.isalnum():
        return "Prefix sadece harf ve rakamlardan oluşmalıdır."

    area_slug = slugify(name)

    if not area_slug:
        return "Alan adı geçerli bir kısa ad üretmelidir."

    try:
        parse_display_order(display_order)
    except ValueError as exc:
        return str(exc)

    existing_name = (
        Area.query
        .filter(Area.name == name, Area.id != area.id)
        .first()
    )

    if existing_name is not None:
        return "Bu alan adı başka bir alanda kullanılıyor."

    existing_slug = (
        Area.query
        .filter(Area.slug == area_slug, Area.id != area.id)
        .first()
    )

    if existing_slug is not None:
        return "Bu alan için oluşan kısa ad başka bir alanda kullanılıyor."

    existing_prefix = (
        Area.query
        .filter(Area.prefix == prefix, Area.id != area.id)
        .first()
    )

    if existing_prefix is not None:
        return "Bu prefix başka bir alanda kullanılıyor."

    if prefix != area.prefix and count_tables_for_area(area.id) > 0:
        return "Altında masa bulunan alanın prefix değeri değiştirilemez."

    if area.is_active and not is_active and count_busy_tables_for_area(area.id) > 0:
        return "Dolu masa bulunan alan pasifleştirilemez."

    return None


def validate_username(username):
    if not username:
        return "Kullanıcı adı zorunludur."

    if len(username) < 3:
        return "Kullanıcı adı en az 3 karakter olmalıdır."

    if " " in username:
        return "Kullanıcı adında boşluk olamaz."

    return None


def validate_password_for_reset(username, password):
    if not password:
        return "Geçici şifre zorunludur."

    if len(password) < 8:
        return "Geçici şifre en az 8 karakter olmalıdır."

    if password == "admin123":
        return "Varsayılan admin şifresi geçici şifre olarak kullanılamaz."

    if password.lower() == username.lower():
        return "Geçici şifre kullanıcı adıyla aynı olamaz."

    return None


def validate_new_user_form(username, full_name, role, password):
    username_error = validate_username(username)

    if username_error:
        return username_error

    if not full_name:
        return "Ad soyad zorunludur."

    if role not in get_role_choices_values():
        return "Geçerli bir rol seçmelisiniz."

    password_error = validate_password_for_reset(username, password)

    if password_error:
        return password_error

    existing_user = User.query.filter_by(username=username).first()

    if existing_user is not None:
        return "Bu kullanıcı adı zaten kullanılıyor."

    return None


def validate_update_user_form(target_user, username, full_name, role, is_active):
    username_error = validate_username(username)

    if username_error:
        return username_error

    if not full_name:
        return "Ad soyad zorunludur."

    if role not in get_role_choices_values():
        return "Geçerli bir rol seçmelisiniz."

    existing_user = (
        User.query
        .filter(User.username == username, User.id != target_user.id)
        .first()
    )

    if existing_user is not None:
        return "Bu kullanıcı adı başka bir kullanıcı tarafından kullanılıyor."

    if target_user.id == current_user.id and username != target_user.username:
        return "Kendi kullanıcı adınızı bu ekrandan değiştiremezsiniz."

    if target_user.id == current_user.id and role != target_user.role:
        return "Kendi rolünüzü değiştiremezsiniz."

    if target_user.id == current_user.id and not is_active:
        return "Kendi hesabınızı pasifleştiremezsiniz."

    if is_last_active_admin(target_user):
        if role != User.ROLE_ADMIN or not is_active:
            return "Son aktif yönetici kullanıcısı pasifleştirilemez veya yönetici rolünden çıkarılamaz."

    return None


def log_user_updated_if_needed(target_user, old_username, old_full_name):
    changed_fields = {}

    if old_username != target_user.username:
        changed_fields["username"] = {
            "old": old_username,
            "new": target_user.username,
        }

    if old_full_name != target_user.full_name:
        changed_fields["full_name"] = {
            "old": old_full_name,
            "new": target_user.full_name,
        }

    if not changed_fields:
        return False

    log_action(
        action_type="user_updated",
        target_type="user",
        target_id=target_user.id,
        target_label=target_user.username,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        role_snapshot=current_user.role,
        description=f"{target_user.username} kullanıcısının temel bilgileri güncellendi.",
        extra_data={
            "changed_fields": changed_fields,
        },
    )

    return True


def log_user_role_changed_if_needed(target_user, old_role):
    if old_role == target_user.role:
        return False

    log_action(
        action_type="user_role_changed",
        target_type="user",
        target_id=target_user.id,
        target_label=target_user.username,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        role_snapshot=current_user.role,
        description=(
            f"{target_user.username} kullanıcısının rolü "
            f"{get_role_label(old_role)} iken {target_user.role_label} olarak değiştirildi."
        ),
        extra_data={
            "old_role": old_role,
            "old_role_label": get_role_label(old_role),
            "new_role": target_user.role,
            "new_role_label": target_user.role_label,
        },
    )

    return True


def log_user_status_changed_if_needed(target_user, old_is_active):
    if old_is_active == target_user.is_active:
        return False

    if target_user.is_active:
        action_type = "user_activated"
        description = f"{target_user.username} kullanıcısı aktif edildi."
    else:
        action_type = "user_deactivated"
        description = f"{target_user.username} kullanıcısı pasifleştirildi."

    log_action(
        action_type=action_type,
        target_type="user",
        target_id=target_user.id,
        target_label=target_user.username,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        role_snapshot=current_user.role,
        description=description,
        extra_data={
            "old_is_active": old_is_active,
            "new_is_active": target_user.is_active,
        },
    )

    return True


def create_tables_for_new_area(area, initial_table_count, default_capacity):
    created_tables = []

    for table_number in range(1, initial_table_count + 1):
        table_code = f"{area.prefix}{table_number}"

        existing_table = Table.query.filter_by(code=table_code).first()

        if existing_table is not None:
            raise ValueError(f"{table_code} masa kodu zaten kullanılıyor.")

        table = Table(
            area_id=area.id,
            code=table_code,
            number=table_number,
            capacity=default_capacity,
            status=Table.STATUS_EMPTY,
            sort_order=table_number,
        )

        db.session.add(table)
        created_tables.append(table)

    return created_tables


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    form_values = {
        "username": "",
        "full_name": "",
        "role": User.ROLE_BAR_STAFF,
    }

    if request.method == "POST":
        username = clean_text(request.form.get("username"))
        full_name = clean_text(request.form.get("full_name"))
        role = clean_text(request.form.get("role"))
        password = request.form.get("password", "")

        form_values = {
            "username": username,
            "full_name": full_name,
            "role": role,
        }

        validation_error = validate_new_user_form(
            username=username,
            full_name=full_name,
            role=role,
            password=password,
        )

        if validation_error:
            flash(validation_error, "danger")
        else:
            new_user = User(
                username=username,
                full_name=full_name,
                role=role,
                is_active=True,
                is_default_password=True,
            )
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.flush()

            log_action(
                action_type="user_created",
                target_type="user",
                target_id=new_user.id,
                target_label=new_user.username,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
                description=(
                    f"{new_user.username} kullanıcısı oluşturuldu. "
                    f"Rol: {new_user.role_label}."
                ),
                extra_data={
                    "created_user_id": new_user.id,
                    "created_username": new_user.username,
                    "created_full_name": new_user.full_name,
                    "created_role": new_user.role,
                    "created_role_label": new_user.role_label,
                    "is_default_password": new_user.is_default_password,
                },
            )

            db.session.commit()

            flash(
                "Kullanıcı oluşturuldu. İlk girişte şifre değiştirmesi istenecek.",
                "success",
            )

            return redirect(url_for("admin.users"))

    user_records = User.query.order_by(User.id.desc()).all()

    return render_template(
        "admin/users.html",
        app_name="Lido Masa Takip Sistemi",
        users=user_records,
        role_choices=ROLE_CHOICES,
        form_values=form_values,
    )


@admin_bp.post("/users/<int:user_id>/update")
@admin_required
def update_user(user_id):
    target_user = get_user_or_redirect(user_id)

    if target_user is None:
        return redirect(url_for("admin.users"))

    username = clean_text(request.form.get("username"))
    full_name = clean_text(request.form.get("full_name"))
    role = clean_text(request.form.get("role"))
    is_active_value = clean_text(request.form.get("is_active"))
    is_active = is_active_value == "1"

    validation_error = validate_update_user_form(
        target_user=target_user,
        username=username,
        full_name=full_name,
        role=role,
        is_active=is_active,
    )

    if validation_error:
        flash(validation_error, "danger")
        return redirect(url_for("admin.users"))

    old_username = target_user.username
    old_full_name = target_user.full_name
    old_role = target_user.role
    old_is_active = target_user.is_active

    target_user.username = username
    target_user.full_name = full_name
    target_user.role = role
    target_user.is_active = is_active

    any_log_written = False
    any_log_written = log_user_updated_if_needed(
        target_user,
        old_username,
        old_full_name,
    ) or any_log_written
    any_log_written = log_user_role_changed_if_needed(
        target_user,
        old_role,
    ) or any_log_written
    any_log_written = log_user_status_changed_if_needed(
        target_user,
        old_is_active,
    ) or any_log_written

    if not any_log_written:
        flash("Kullanıcı bilgilerinde değişiklik yok.", "info")
        return redirect(url_for("admin.users"))

    db.session.commit()

    flash("Kullanıcı bilgileri güncellendi.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/toggle-active")
@admin_required
def toggle_user_active(user_id):
    target_user = get_user_or_redirect(user_id)

    if target_user is None:
        return redirect(url_for("admin.users"))

    if target_user.id == current_user.id:
        flash("Kendi hesabınızı pasifleştiremezsiniz.", "danger")
        return redirect(url_for("admin.users"))

    new_is_active = not target_user.is_active

    if not new_is_active and is_last_active_admin(target_user):
        flash("Son aktif yönetici kullanıcısı pasifleştirilemez.", "danger")
        return redirect(url_for("admin.users"))

    old_is_active = target_user.is_active
    target_user.is_active = new_is_active

    log_user_status_changed_if_needed(target_user, old_is_active)

    db.session.commit()

    if target_user.is_active:
        flash("Kullanıcı aktif edildi.", "success")
    else:
        flash("Kullanıcı pasifleştirildi.", "success")

    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/reset-password")
@admin_required
def reset_user_password(user_id):
    target_user = get_user_or_redirect(user_id)

    if target_user is None:
        return redirect(url_for("admin.users"))

    temporary_password = request.form.get("temporary_password", "")

    validation_error = validate_password_for_reset(
        target_user.username,
        temporary_password,
    )

    if validation_error:
        flash(validation_error, "danger")
        return redirect(url_for("admin.users"))

    target_user.set_password(temporary_password)
    target_user.is_default_password = True

    log_action(
        action_type="user_password_reset",
        target_type="user",
        target_id=target_user.id,
        target_label=target_user.username,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        role_snapshot=current_user.role,
        description=(
            f"{target_user.username} kullanıcısının şifresi sıfırlandı. "
            "Kullanıcı ilk girişte yeni şifre belirleyecek."
        ),
        extra_data={
            "target_username": target_user.username,
            "target_role": target_user.role,
            "target_role_label": target_user.role_label,
            "is_default_password": target_user.is_default_password,
        },
    )

    db.session.commit()

    flash("Kullanıcı şifresi sıfırlandı. İlk girişte şifre değiştirmesi istenecek.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/tables", methods=["GET", "POST"])
@admin_required
def tables():
    areas = Area.query.order_by(Area.display_order.asc(), Area.id.asc()).all()
    active_areas = [area for area in areas if area.is_active]
    selected_area_slug = clean_text(request.args.get("area"))

    selected_area = None

    if selected_area_slug:
        selected_area = Area.query.filter_by(slug=selected_area_slug).first()

    if selected_area is None and active_areas:
        selected_area = active_areas[0]

    if selected_area is None and areas:
        selected_area = areas[0]

    table_form_values = {
        "area_id": str(selected_area.id) if selected_area else "",
        "code": "",
        "capacity": "4",
        "status": Table.STATUS_EMPTY,
    }

    area_form_values = {
        "name": "",
        "prefix": "",
        "display_order": str(len(areas) + 1),
        "initial_table_count": "0",
        "default_capacity": "4",
    }

    if request.method == "POST":
        form_action = clean_text(request.form.get("form_action"))

        if form_action == "create_area":
            area_name = clean_text(request.form.get("area_name"))
            prefix = normalize_prefix(request.form.get("prefix"))
            display_order_value = clean_text(request.form.get("display_order"))
            initial_table_count_value = clean_text(request.form.get("initial_table_count"))
            default_capacity_value = clean_text(request.form.get("default_capacity"))

            area_form_values = {
                "name": area_name,
                "prefix": prefix,
                "display_order": display_order_value,
                "initial_table_count": initial_table_count_value,
                "default_capacity": default_capacity_value,
            }

            validation_error = validate_area_create_form(
                name=area_name,
                prefix=prefix,
                display_order=display_order_value,
                initial_table_count=initial_table_count_value,
                default_capacity=default_capacity_value,
            )

            if validation_error:
                flash(validation_error, "danger")
            else:
                try:
                    display_order = parse_display_order(display_order_value)
                    initial_table_count = parse_initial_table_count(initial_table_count_value)
                    default_capacity = parse_capacity(default_capacity_value)

                    area = Area(
                        name=area_name,
                        slug=slugify(area_name),
                        prefix=prefix,
                        table_count=initial_table_count,
                        display_order=display_order,
                        is_active=True,
                    )

                    db.session.add(area)
                    db.session.flush()

                    created_tables = create_tables_for_new_area(
                        area=area,
                        initial_table_count=initial_table_count,
                        default_capacity=default_capacity,
                    )

                    db.session.flush()

                    log_action(
                        action_type="area_created",
                        target_type="area",
                        target_id=area.id,
                        target_label=area.name,
                        user_id=current_user.id,
                        username_snapshot=current_user.username,
                        role_snapshot=current_user.role,
                        description=(
                            f"{area.name} alanı oluşturuldu. "
                            f"Prefix: {area.prefix}. "
                            f"Oluşturulan masa sayısı: {len(created_tables)}."
                        ),
                        extra_data={
                            "area_id": area.id,
                            "area_name": area.name,
                            "area_slug": area.slug,
                            "prefix": area.prefix,
                            "display_order": area.display_order,
                            "initial_table_count": initial_table_count,
                            "default_capacity": default_capacity,
                            "created_table_count": len(created_tables),
                        },
                    )

                    db.session.commit()

                    flash("Yeni alan oluşturuldu.", "success")
                    return redirect(url_for("admin.tables", area=area.slug))

                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")

        elif form_action == "create_table":
            area_id = clean_text(request.form.get("area_id"))
            table_code = normalize_table_code(request.form.get("code"))
            capacity_value = clean_text(request.form.get("capacity"))
            status = clean_text(request.form.get("status"))

            table_form_values = {
                "area_id": area_id,
                "code": table_code,
                "capacity": capacity_value,
                "status": status,
            }

            area = db.session.get(Area, int(area_id)) if area_id.isdigit() else None

            try:
                if area is None:
                    raise ValueError("Geçerli bir alan seçmelisiniz.")

                if not area.is_active:
                    raise ValueError("Pasif alana masa eklenemez.")

                capacity = parse_capacity(capacity_value)
                table_number = parse_table_number_from_code(area, table_code)

                if status not in [Table.STATUS_EMPTY, Table.STATUS_INACTIVE]:
                    raise ValueError("Yeni masa durumu sadece aktif/boş veya pasif olabilir.")

                existing_table = Table.query.filter_by(code=table_code).first()

                if existing_table is not None:
                    raise ValueError("Bu masa kodu zaten kullanılıyor.")

                new_table = Table(
                    area_id=area.id,
                    code=table_code,
                    number=table_number,
                    capacity=capacity,
                    status=status,
                    sort_order=table_number,
                )

                db.session.add(new_table)

                if table_number > area.table_count:
                    area.table_count = table_number

                db.session.flush()

                log_action(
                    action_type="table_created",
                    target_type="table",
                    target_id=new_table.id,
                    target_label=new_table.code,
                    user_id=current_user.id,
                    username_snapshot=current_user.username,
                    role_snapshot=current_user.role,
                    description=(
                        f"{new_table.code} masası {area.name} alanına "
                        f"{capacity} kişilik olarak oluşturuldu."
                    ),
                    extra_data={
                        "table_id": new_table.id,
                        "table_code": new_table.code,
                        "area_id": area.id,
                        "area_name": area.name,
                        "capacity": capacity,
                        "status": status,
                        "status_label": get_table_status_label(status),
                    },
                )

                db.session.commit()

                flash("Yeni masa oluşturuldu.", "success")
                return redirect(url_for("admin.tables", area=area.slug))

            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "danger")
        else:
            flash("Geçersiz form işlemi.", "danger")

    table_query = Table.query.join(Area)

    if selected_area is not None:
        table_query = table_query.filter(Table.area_id == selected_area.id)

    table_records = (
        table_query
        .order_by(Area.display_order.asc(), Table.sort_order.asc(), Table.id.asc())
        .all()
    )

    table_views = [build_table_view_model(table) for table in table_records]
    area_summaries = [build_area_summary_view_model(area) for area in areas]

    return render_template(
        "admin/tables.html",
        app_name="Lido Masa Takip Sistemi",
        areas=areas,
        active_areas=active_areas,
        selected_area=selected_area,
        selected_area_slug=selected_area.slug if selected_area else "",
        area_summaries=area_summaries,
        tables=table_views,
        status_choices=TABLE_STATUS_CHOICES,
        table_form_values=table_form_values,
        area_form_values=area_form_values,
    )


@admin_bp.post("/areas/<int:area_id>/update")
@admin_required
def update_area(area_id):
    area = get_area_or_redirect(area_id)

    if area is None:
        return redirect(url_for("admin.tables"))

    area_name = clean_text(request.form.get("area_name"))
    prefix = normalize_prefix(request.form.get("prefix"))
    display_order_value = clean_text(request.form.get("display_order"))
    is_active_value = clean_text(request.form.get("is_active"))
    is_active = is_active_value == "1"

    validation_error = validate_area_update_form(
        area=area,
        name=area_name,
        prefix=prefix,
        display_order=display_order_value,
        is_active=is_active,
    )

    if validation_error:
        flash(validation_error, "danger")
        return redirect(url_for("admin.tables", area=area.slug))

    old_name = area.name
    old_slug = area.slug
    old_prefix = area.prefix
    old_display_order = area.display_order
    old_is_active = area.is_active

    area.name = area_name
    area.slug = slugify(area_name)
    area.prefix = prefix
    area.display_order = parse_display_order(display_order_value)
    area.is_active = is_active

    changed_fields = {}

    if old_name != area.name:
        changed_fields["name"] = {
            "old": old_name,
            "new": area.name,
        }

    if old_slug != area.slug:
        changed_fields["slug"] = {
            "old": old_slug,
            "new": area.slug,
        }

    if old_prefix != area.prefix:
        changed_fields["prefix"] = {
            "old": old_prefix,
            "new": area.prefix,
        }

    if old_display_order != area.display_order:
        changed_fields["display_order"] = {
            "old": old_display_order,
            "new": area.display_order,
        }

    any_log_written = False

    if changed_fields:
        any_log_written = True

        log_action(
            action_type="area_updated",
            target_type="area",
            target_id=area.id,
            target_label=area.name,
            user_id=current_user.id,
            username_snapshot=current_user.username,
            role_snapshot=current_user.role,
            description=f"{area.name} alan bilgileri güncellendi.",
            extra_data={
                "changed_fields": changed_fields,
            },
        )

    if old_is_active != area.is_active:
        any_log_written = True

        if area.is_active:
            action_type = "area_activated"
            description = f"{area.name} alanı aktif edildi."
        else:
            action_type = "area_deactivated"
            description = f"{area.name} alanı pasifleştirildi."

        log_action(
            action_type=action_type,
            target_type="area",
            target_id=area.id,
            target_label=area.name,
            user_id=current_user.id,
            username_snapshot=current_user.username,
            role_snapshot=current_user.role,
            description=description,
            extra_data={
                "old_is_active": old_is_active,
                "new_is_active": area.is_active,
            },
        )

    if not any_log_written:
        flash("Alan bilgilerinde değişiklik yok.", "info")
        return redirect(url_for("admin.tables", area=area.slug))

    db.session.commit()

    flash("Alan bilgileri güncellendi.", "success")
    return redirect(url_for("admin.tables", area=area.slug))


@admin_bp.post("/areas/<int:area_id>/toggle-active")
@admin_required
def toggle_area_active(area_id):
    area = get_area_or_redirect(area_id)

    if area is None:
        return redirect(url_for("admin.tables"))

    new_is_active = not area.is_active

    if not new_is_active and count_busy_tables_for_area(area.id) > 0:
        flash("Dolu masa bulunan alan pasifleştirilemez.", "danger")
        return redirect(url_for("admin.tables", area=area.slug))

    old_is_active = area.is_active
    area.is_active = new_is_active

    if area.is_active:
        action_type = "area_activated"
        description = f"{area.name} alanı aktif edildi."
    else:
        action_type = "area_deactivated"
        description = f"{area.name} alanı pasifleştirildi."

    log_action(
        action_type=action_type,
        target_type="area",
        target_id=area.id,
        target_label=area.name,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        role_snapshot=current_user.role,
        description=description,
        extra_data={
            "old_is_active": old_is_active,
            "new_is_active": area.is_active,
        },
    )

    db.session.commit()

    if area.is_active:
        flash("Alan aktif edildi.", "success")
    else:
        flash("Alan pasifleştirildi.", "success")

    return redirect(url_for("admin.tables", area=area.slug))


@admin_bp.post("/areas/<int:area_id>/delete")
@admin_required
def delete_area(area_id):
    area = get_area_or_redirect(area_id)

    if area is None:
        return redirect(url_for("admin.tables"))

    busy_table_count = count_busy_tables_for_area(area.id)
    session_count = count_table_sessions_for_area(area.id)

    if busy_table_count > 0:
        flash("Dolu masa bulunan alan silinemez. Önce masaları boşaltın.", "danger")
        return redirect(url_for("admin.tables", area=area.slug))

    if session_count > 0:
        flash(
            "Bu alanda müşteri geçmişi bulunduğu için kalıcı silme yapılamaz. Alanı pasifleştirebilirsiniz.",
            "danger",
        )
        return redirect(url_for("admin.tables", area=area.slug))

    area_name = area.name
    area_slug = area.slug
    area_prefix = area.prefix
    table_count = count_tables_for_area(area.id)

    log_action(
        action_type="area_deleted",
        target_type="area",
        target_id=area.id,
        target_label=area.name,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        role_snapshot=current_user.role,
        description=f"{area.name} alanı kalıcı olarak silindi. Silinen masa sayısı: {table_count}.",
        extra_data={
            "area_id": area.id,
            "area_name": area_name,
            "area_slug": area_slug,
            "area_prefix": area_prefix,
            "deleted_table_count": table_count,
        },
    )

    db.session.delete(area)
    db.session.commit()

    flash("Alan kalıcı olarak silindi.", "success")
    return redirect(url_for("admin.tables"))


@admin_bp.post("/tables/<int:table_id>/update")
@admin_required
def update_table(table_id):
    table = get_table_or_redirect(table_id)

    if table is None:
        return redirect(url_for("admin.tables"))

    capacity_value = clean_text(request.form.get("capacity"))
    status = clean_text(request.form.get("status"))

    try:
        capacity = parse_capacity(capacity_value)

        if table.status in [Table.STATUS_OCCUPIED, Table.STATUS_LONG]:
            if status != table.status:
                raise ValueError("Dolu masanın durumu bu ekrandan değiştirilemez.")
        else:
            if status not in [Table.STATUS_EMPTY, Table.STATUS_INACTIVE]:
                raise ValueError("Masa durumu sadece aktif/boş veya pasif olarak değiştirilebilir.")

        if table.status in [Table.STATUS_OCCUPIED, Table.STATUS_LONG] and status == Table.STATUS_INACTIVE:
            raise ValueError("Dolu masa pasif yapılamaz. Önce masa boşaltılmalıdır.")

        old_capacity = table.capacity
        old_status = table.status

        table.capacity = capacity

        if table.status == Table.STATUS_INACTIVE and status == Table.STATUS_EMPTY:
            table.status = Table.STATUS_EMPTY
        elif table.status == Table.STATUS_EMPTY and status == Table.STATUS_INACTIVE:
            table.status = Table.STATUS_INACTIVE

        any_change = False

        if old_capacity != table.capacity:
            any_change = True

            log_action(
                action_type="table_capacity_updated",
                target_type="table",
                target_id=table.id,
                target_label=table.code,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
                description=(
                    f"{table.code} masa kapasitesi "
                    f"{old_capacity} kişiden {table.capacity} kişiye güncellendi."
                ),
                extra_data={
                    "table_id": table.id,
                    "table_code": table.code,
                    "old_capacity": old_capacity,
                    "new_capacity": table.capacity,
                    "area_name": table.area.name,
                },
            )

        if old_status != table.status:
            any_change = True

            if table.status == Table.STATUS_INACTIVE:
                action_type = "table_deactivated"
                description = f"{table.code} masası pasif hale getirildi."
            else:
                action_type = "table_activated"
                description = f"{table.code} masası aktif hale getirildi."

            log_action(
                action_type=action_type,
                target_type="table",
                target_id=table.id,
                target_label=table.code,
                user_id=current_user.id,
                username_snapshot=current_user.username,
                role_snapshot=current_user.role,
                description=description,
                extra_data={
                    "table_id": table.id,
                    "table_code": table.code,
                    "old_status": old_status,
                    "old_status_label": get_table_status_label(old_status),
                    "new_status": table.status,
                    "new_status_label": get_table_status_label(table.status),
                    "area_name": table.area.name,
                },
            )

        if not any_change:
            flash("Masa bilgilerinde değişiklik yok.", "info")
            return redirect(url_for("admin.tables", area=table.area.slug))

        db.session.commit()

        flash("Masa bilgileri güncellendi.", "success")
        return redirect(url_for("admin.tables", area=table.area.slug))

    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("admin.tables", area=table.area.slug))


@admin_bp.route("/action-logs", methods=["GET"])
@admin_required
def action_logs():
    action_log_records = (
        ActionLog.query
        .order_by(ActionLog.id.desc())
        .limit(100)
        .all()
    )

    action_logs_view = [
        build_action_log_view_model(action_log)
        for action_log in action_log_records
    ]

    return render_template(
        "admin/action_logs.html",
        app_name="Lido Masa Takip Sistemi",
        action_logs=action_logs_view,
    )