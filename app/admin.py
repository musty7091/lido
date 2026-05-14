from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import log_action
from app.extensions import db
from app.models import User
from app.permissions import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def validate_new_user_form(username, full_name, role, password):
    if not username:
        return "Kullanıcı adı zorunludur."

    if len(username) < 3:
        return "Kullanıcı adı en az 3 karakter olmalıdır."

    if " " in username:
        return "Kullanıcı adında boşluk olamaz."

    if not full_name:
        return "Ad soyad zorunludur."

    valid_roles = [role_choice["value"] for role_choice in ROLE_CHOICES]

    if role not in valid_roles:
        return "Geçerli bir rol seçmelisiniz."

    if not password:
        return "Geçici şifre zorunludur."

    if len(password) < 8:
        return "Geçici şifre en az 8 karakter olmalıdır."

    existing_user = User.query.filter_by(username=username).first()

    if existing_user is not None:
        return "Bu kullanıcı adı zaten kullanılıyor."

    return None


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