from functools import wraps

from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from app.models import User


def create_permission_error_response(message, status_code=403):
    if request.path.startswith("/api/"):
        return jsonify(
            {
                "success": False,
                "message": message,
            }
        ), status_code

    flash(message, "danger")
    return redirect(url_for("index"))


def admin_required(view_function):
    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return create_permission_error_response(
                "Bu işlem için giriş yapmalısınız.",
                401,
            )

        if not current_user.is_active:
            return create_permission_error_response(
                "Kullanıcı hesabınız pasif durumda.",
                403,
            )

        if current_user.role != User.ROLE_ADMIN:
            return create_permission_error_response(
                "Bu işlem için yönetici yetkisi gerekir.",
                403,
            )

        return view_function(*args, **kwargs)

    return wrapped_view


def staff_required(view_function):
    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return create_permission_error_response(
                "Bu işlem için giriş yapmalısınız.",
                401,
            )

        if not current_user.is_active:
            return create_permission_error_response(
                "Kullanıcı hesabınız pasif durumda.",
                403,
            )

        allowed_roles = {
            User.ROLE_ADMIN,
            User.ROLE_DOOR_STAFF,
            User.ROLE_BAR_STAFF,
        }

        if current_user.role not in allowed_roles:
            return create_permission_error_response(
                "Bu işlem için personel yetkisi gerekir.",
                403,
            )

        return view_function(*args, **kwargs)

    return wrapped_view