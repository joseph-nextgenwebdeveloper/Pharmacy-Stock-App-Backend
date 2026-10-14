from calendar import monthrange
from datetime import date, datetime, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import ActivityLog
from inventory.models import Batch, Medicine, StockMovement
from sales.models import SaleItem


def get_inventory_report():
    report = []

    for medicine in Medicine.objects.all():
        quantity = (
            medicine.batches.aggregate(total=Sum("quantity"))["total"] or 0
        )

        if quantity == 0:
            status = "OUT_OF_STOCK"
        elif quantity <= medicine.reorder_level:
            status = "LOW_STOCK"
        else:
            status = "HEALTHY"

        report.append({
            "medicine": medicine.name,
            "sku": medicine.sku,
            "quantity": quantity,
            "reorder_level": medicine.reorder_level,
            "status": status,
        })

    return report


def get_monthly_movement_report(year, month):
    movements = StockMovement.objects.filter(
        movement_date__year=year,
        movement_date__month=month,
    )

    received = (
        movements.filter(movement_type="IN")
        .aggregate(total=Sum("quantity"))["total"] or 0
    )

    dispensed = (
        movements.filter(movement_type="OUT")
        .aggregate(total=Sum("quantity"))["total"] or 0
    )

    return {
        "year": year,
        "month": month,
        "stock_received": received,
        "stock_dispensed": dispensed,
    }


def get_expired_medicines():
    today = timezone.localdate()

    batches = Batch.objects.filter(
        expiry_date__lt=today,
        quantity__gt=0,
    ).select_related("medicine")

    return [
        {
            "medicine": batch.medicine.name,
            "sku": batch.medicine.sku,
            "batch_number": batch.batch_number,
            "expiry_date": batch.expiry_date,
            "quantity": batch.quantity,
        }
        for batch in batches
    ]


def get_stock_valuation():
    report = []

    for medicine in Medicine.objects.all():
        batches = medicine.batches.all()

        quantity = (
            batches.aggregate(total=Sum("quantity"))["total"] or 0
        )

        value = sum(
            batch.quantity * batch.buying_price
            for batch in batches
        )

        report.append({
            "medicine": medicine.name,
            "sku": medicine.sku,
            "quantity": quantity,
            "stock_value": value,
        })

    return report


def get_fast_moving_medicines():
    movements = (
        SaleItem.objects
        .values("medicine", "medicine__name", "medicine__sku")
        .annotate(total_dispensed=Sum("quantity"))
        .order_by("-total_dispensed")
    )

    return [
        {
            "medicine": item["medicine__name"],
            "sku": item["medicine__sku"],
            "quantity_dispensed": item["total_dispensed"],
        }
        for item in movements
    ]


def get_slow_moving_medicines():
    movements = (
        SaleItem.objects
        .values("medicine", "medicine__name", "medicine__sku")
        .annotate(total_dispensed=Sum("quantity"))
        .order_by("total_dispensed")
    )

    return [
        {
            "medicine": item["medicine__name"],
            "sku": item["medicine__sku"],
            "quantity_dispensed": item["total_dispensed"],
        }
        for item in movements
    ]


# ----------------------------------------------------------------------
# Movement & activity report (day / week / month / any custom range)
# ----------------------------------------------------------------------

MAX_REPORT_DAYS = 366
MAX_MOVEMENT_ROWS = 5000


def _parse_day(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return default


def resolve_period(period, anchor=None, start=None, end=None):
    """Turns (period, date) into an inclusive (start, end) pair of local dates.

    day    -> that day
    week   -> Monday..Sunday of the week containing the date
    month  -> 1st..last day of that month
    custom -> start..end as given
    """
    today = timezone.localdate()
    anchor = _parse_day(anchor, today)
    period = (period or "day").lower()

    if period == "week":
        first = anchor - timedelta(days=anchor.weekday())
        return "week", first, first + timedelta(days=6)

    if period == "month":
        last = monthrange(anchor.year, anchor.month)[1]
        return "month", anchor.replace(day=1), anchor.replace(day=last)

    if period == "custom":
        first = _parse_day(start, anchor)
        last = _parse_day(end, first)
        if last < first:
            first, last = last, first
        if (last - first).days + 1 > MAX_REPORT_DAYS:
            last = first + timedelta(days=MAX_REPORT_DAYS - 1)
        return "custom", first, last

    return "day", anchor, anchor


def _label(period, start, end):
    if period == "day" or start == end:
        return f"{start:%A, %d %B %Y}"
    if period == "month":
        return f"{start:%B %Y}"
    if start.year == end.year:
        return f"{start:%d %b} - {end:%d %b %Y}"
    return f"{start:%d %b %Y} - {end:%d %b %Y}"


def get_activity_report(user, period="day", anchor=None, start=None, end=None,
                        can_see_team=False):
    """Everything that happened between two dates, ready to print.

    * stock movements (the ledger) - visible to every signed-in staff member,
      the same as the movement history screen;
    * other activity (medicines / batches / suppliers created or edited) -
      the whole team for admins and store managers, otherwise only the
      person's own.
    """
    period, first, last = resolve_period(period, anchor, start, end)

    moves = (
        StockMovement.objects.filter(
            movement_date__date__gte=first, movement_date__date__lte=last
        )
        .select_related("medicine", "batch", "performed_by")
        .order_by("movement_date", "id")
    )

    totals = moves.aggregate(
        units_in=Sum("quantity", filter=Q(movement_type="IN")),
        units_out=Sum("quantity", filter=Q(movement_type="OUT")),
        count=Count("id"),
    )
    units_in = totals["units_in"] or 0
    units_out = totals["units_out"] or 0

    # ---- per day (every day in the range, so quiet days show as 0) ----
    per_day = {}
    for m in moves:
        day = timezone.localtime(m.movement_date).date()
        row = per_day.setdefault(day, {"units_in": 0, "units_out": 0, "moves": 0})
        row["moves"] += 1
        if m.movement_type == "IN":
            row["units_in"] += m.quantity
        else:
            row["units_out"] += m.quantity

    daily = []
    day = first
    while day <= last:
        row = per_day.get(day, {"units_in": 0, "units_out": 0, "moves": 0})
        daily.append({"date": day.isoformat(), **row})
        day += timedelta(days=1)

    # ---- per medicine / reason / staff ----
    by_medicine, by_reason, by_staff = {}, {}, {}
    reason_labels = dict(StockMovement.REASON_CHOICES)

    for m in moves:
        med = by_medicine.setdefault(
            m.medicine_id,
            {
                "medicine_id": m.medicine_id,
                "medicine": m.medicine.name,
                "sku": m.medicine.sku,
                "units_in": 0,
                "units_out": 0,
                "moves": 0,
            },
        )
        med["moves"] += 1

        reason = m.effective_reason
        why = by_reason.setdefault(
            (m.movement_type, reason),
            {
                "movement_type": m.movement_type,
                "reason": reason,
                "label": reason_labels.get(reason, reason.title()),
                "units": 0,
                "moves": 0,
            },
        )
        why["moves"] += 1

        who = by_staff.setdefault(
            m.performed_by_id,
            {
                "user": m.performed_by_id,
                "name": m.performed_by.display_name,
                "role": m.performed_by.role,
                "moves": 0,
                "units_in": 0,
                "units_out": 0,
            },
        )
        who["moves"] += 1

        if m.movement_type == "IN":
            med["units_in"] += m.quantity
            who["units_in"] += m.quantity
        else:
            med["units_out"] += m.quantity
            who["units_out"] += m.quantity
        why["units"] += m.quantity

    medicines = sorted(
        by_medicine.values(),
        key=lambda r: (-(r["units_in"] + r["units_out"]), r["medicine"]),
    )
    for r in medicines:
        r["net"] = r["units_in"] - r["units_out"]

    reasons = sorted(by_reason.values(), key=lambda r: (r["movement_type"], -r["units"]))
    staff = sorted(by_staff.values(), key=lambda r: -r["moves"])

    # ---- the ledger itself ----
    movement_rows = []
    for m in list(moves[:MAX_MOVEMENT_ROWS]):
        movement_rows.append(
            {
                "id": m.id,
                "at": timezone.localtime(m.movement_date).isoformat(),
                "medicine": m.medicine.name,
                "sku": m.medicine.sku,
                "batch": m.batch.batch_number,
                "movement_type": m.movement_type,
                "reason": m.effective_reason,
                "reason_label": reason_labels.get(m.effective_reason, ""),
                "quantity": m.quantity,
                "before": m.quantity_before,
                "after": m.quantity_after,
                "reference": m.reference,
                "note": m.note,
                "by": m.performed_by.display_name,
            }
        )

    # ---- other activity (not stock, not sign-in noise) ----
    acts = ActivityLog.objects.filter(
        created_at__date__gte=first, created_at__date__lte=last
    ).exclude(
        action__in=[
            ActivityLog.LOGIN,
            ActivityLog.LOGOUT,
            ActivityLog.STOCK_IN,
            ActivityLog.STOCK_OUT,
        ]
    )
    if not can_see_team:
        acts = acts.filter(user=user)

    activity_rows = [
        {
            "at": timezone.localtime(a.created_at).isoformat(),
            "by": a.user_name or "System",
            "action": a.action,
            "action_label": a.get_action_display(),
            "summary": a.summary,
        }
        for a in acts.order_by("created_at", "id")[:2000]
    ]

    return {
        "period": period,
        "start": first.isoformat(),
        "end": last.isoformat(),
        "label": _label(period, first, last),
        "generated_at": timezone.localtime().isoformat(),
        "scope": "team" if can_see_team else "mine",
        "summary": {
            "movements": totals["count"] or 0,
            "units_in": units_in,
            "units_out": units_out,
            "net": units_in - units_out,
            "medicines_touched": len(medicines),
            "staff_active": len(staff),
            "other_activities": len(activity_rows),
            "truncated": (totals["count"] or 0) > MAX_MOVEMENT_ROWS,
        },
        "daily": daily,
        "by_medicine": medicines,
        "by_reason": reasons,
        "by_staff": staff,
        "movements": movement_rows,
        "activities": activity_rows,
    }
