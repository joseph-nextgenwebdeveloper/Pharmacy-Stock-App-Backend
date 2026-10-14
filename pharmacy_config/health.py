from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    """Liveness ping for cron jobs / uptime monitors.

    No auth, no database, nothing else in the body - just {"status": "ok"}.
    GET and HEAD are both allowed (many cron services ping with HEAD).
    """
    return JsonResponse({"status": "ok"})
