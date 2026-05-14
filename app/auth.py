from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.audit import log_action
from app.extensions import db
from app.models import User, utc_now

auth_bp = Blueprint("auth", __name__)


def is_safe_next_url(next_url):
    if not next_url:
        return False

    parsed_url = urlparse(next_url)

    if parsed_url.netloc:
        return False

    if not parsed_url.path.startswith("/"):
        return False

    if parsed_url.path.startswith("//"):
        return False

    return True


def validate_new_password(user, new_password, confirm_password):
    if not new_password:
        return "Yeni şifre boş olamaz."

    if len(new_password) < 8:
        return "Yeni şifre en az 8 karakter olmalıdır."

    if new_password != confirm_password:
        return "Yeni şifre ve tekrar şifre aynı olmalıdır."

    if new_password == "admin123":
        return "Varsayılan şifre tekrar kullanılamaz."

    if new_password.lower() == user.username.lower():
        return "Şifre kullanıcı adıyla aynı olamaz."

    if user.check_password(new_password):
        return "Yeni şifre mevcut şifreyle aynı olamaz."

    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_default_password:
            return redirect(url_for("auth.change_password"))

        return redirect(url_for("index"))

    next_url = request.args.get("next")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            log_action(
                action_type="login_failed",
                target_type="user",
                target_label=username or "empty_username",
                username_snapshot=username or None,
                role_snapshot=None,
                description="Başarısız giriş denemesi.",
                extra_data={
                    "reason": "invalid_username_or_password",
                },
                commit=True,
            )

            flash("Kullanıcı adı veya şifre hatalı.", "danger")
            return render_template(
                "auth/login.html",
                app_name="Lido Masa Takip Sistemi",
                username=username,
                next_url=next_url,
            )

        if not user.is_active:
            log_action(
                action_type="login_blocked",
                target_type="user",
                target_id=user.id,
                target_label=user.username,
                user_id=user.id,
                username_snapshot=user.username,
                role_snapshot=user.role,
                description="Pasif kullanıcı giriş yapmaya çalıştı.",
                extra_data={
                    "reason": "inactive_user",
                },
                commit=True,
            )

            flash("Bu kullanıcı pasif durumda. Yönetici ile görüşün.", "danger")
            return render_template(
                "auth/login.html",
                app_name="Lido Masa Takip Sistemi",
                username=username,
                next_url=next_url,
            )

        user.last_login_at = utc_now()

        log_action(
            action_type="login_success",
            target_type="user",
            target_id=user.id,
            target_label=user.username,
            user_id=user.id,
            username_snapshot=user.username,
            role_snapshot=user.role,
            description="Kullanıcı sisteme giriş yaptı.",
        )

        db.session.commit()

        login_user(user)

        if user.is_default_password:
            flash("Güvenlik için varsayılan şifrenizi değiştirmeniz gerekiyor.", "warning")
            return redirect(url_for("auth.change_password"))

        requested_next_url = request.form.get("next") or next_url

        if is_safe_next_url(requested_next_url):
            return redirect(requested_next_url)

        return redirect(url_for("index"))

    return render_template(
        "auth/login.html",
        app_name="Lido Masa Takip Sistemi",
        username="",
        next_url=next_url,
    )


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Mevcut şifre hatalı.", "danger")
            return render_template(
                "auth/change_password.html",
                app_name="Lido Masa Takip Sistemi",
            )

        validation_error = validate_new_password(
            current_user,
            new_password,
            confirm_password,
        )

        if validation_error:
            flash(validation_error, "danger")
            return render_template(
                "auth/change_password.html",
                app_name="Lido Masa Takip Sistemi",
            )

        current_user.set_password(new_password)
        current_user.is_default_password = False

        log_action(
            action_type="password_changed",
            target_type="user",
            target_id=current_user.id,
            target_label=current_user.username,
            user_id=current_user.id,
            username_snapshot=current_user.username,
            role_snapshot=current_user.role,
            description="Kullanıcı şifresini değiştirdi.",
        )

        db.session.commit()

        flash("Şifreniz başarıyla değiştirildi.", "success")
        return redirect(url_for("index"))

    return render_template(
        "auth/change_password.html",
        app_name="Lido Masa Takip Sistemi",
    )


@auth_bp.post("/logout")
@login_required
def logout():
    username = current_user.username
    role = current_user.role
    user_id = current_user.id

    log_action(
        action_type="logout",
        target_type="user",
        target_id=user_id,
        target_label=username,
        user_id=user_id,
        username_snapshot=username,
        role_snapshot=role,
        description="Kullanıcı sistemden çıkış yaptı.",
        commit=True,
    )

    logout_user()

    return redirect(url_for("auth.login"))