from flask import has_request_context, request

from app.extensions import db
from app.models import ActionLog


def get_request_ip_address():
    if not has_request_context():
        return None

    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.remote_addr


def get_request_user_agent():
    if not has_request_context():
        return None

    return request.headers.get("User-Agent")


def log_action(
    action_type,
    description,
    target_type=None,
    target_id=None,
    target_label=None,
    user_id=None,
    username_snapshot=None,
    role_snapshot=None,
    extra_data=None,
    commit=False,
):
    action_log = ActionLog(
        user_id=user_id,
        username_snapshot=username_snapshot,
        role_snapshot=role_snapshot,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        description=description,
        ip_address=get_request_ip_address(),
        user_agent=get_request_user_agent(),
        extra_data=extra_data,
    )

    db.session.add(action_log)

    if commit:
        db.session.commit()

    return action_log