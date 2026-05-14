from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import log_action
from app.extensions import db
from app.models import ActionLog, User
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
    "table_assigned": "Masa Atandı",
    "table_cleared": "Masa Boşaltıldı",
    "table_transferred": "Masa Transferi",
}


ROLE_LABELS = {
    User.ROLE_ADMIN: "Yönetici",
    User.ROLE_DOOR_STAFF: "Kapı Personeli",
    User.ROLE_BAR_STAFF: "Bar Personeli",
    "system": "Sistem",
}


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


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


def get_role_choices_values():
    return [role_choice["value"] for role_choice in ROLE_CHOICES]


def get_user_or_redirect(user_id):
    user = db.session.get(User, user_id)

    if user is None:
        flash("Kullanıcı bulunamadı.", "danger")
        return None

    return user


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