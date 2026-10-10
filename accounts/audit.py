"""Tiny helper every part of the backend uses to record "who did what".

`log_activity` must never break the real action it is describing, so it
swallows its own errors (inside a savepoint, so a failure can't poison the
surrounding database transaction).
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def snapshot(instance, fields):
    """Plain, JSON-safe copy of the given fields of a model instance."""
    data = {}
    for name in fields:
        value = getattr(instance, name, None)
        if value is None or isinstance(value, (bool, int, float, str)):
            data[name] = value
        elif hasattr(value, "pk"):
            data[name] = str(value)
        elif hasattr(value, "name") and not isinstance(value, (bytes,)):
            data[name] = value.name or ""  # FieldFile
        else:
            data[name] = str(value)
    return data


def diff(before, after):
    """{field: {"from": old, "to": new}} for every field that changed."""
    changes = {}
    for key, new in after.items():
        old = before.get(key)
        if old != new:
            changes[key] = {"from": old, "to": new}
    return changes


def log_activity(
    user,
    action,
    summary,
    *,
    target=None,
    target_type="",
    target_id=None,
    target_label="",
    quantity=None,
    changes=None,
):
    from .models import ActivityLog  # local import: avoids app-loading cycles

    try:
        if target is not None:
            target_type = target_type or target.__class__.__name__
            if target_id is None:
                target_id = getattr(target, "pk", None)
            target_label = target_label or str(target)

        has_user = bool(user is not None and getattr(user, "pk", None))

        with transaction.atomic():
            return ActivityLog.objects.create(
                user=user if has_user else None,
                user_name=(user.display_name if has_user else "")[:150],
                user_role=(getattr(user, "role", "") if has_user else "")[:20],
                action=action,
                summary=str(summary)[:255],
                target_type=target_type[:40],
                target_id=target_id,
                target_label=str(target_label)[:255],
                quantity=quantity,
                changes=changes or {},
            )
    except Exception:  # pragma: no cover - logging must never break the action
        logger.exception("Could not record activity %s", action)
        return None
