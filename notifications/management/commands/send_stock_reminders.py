from django.core.management.base import BaseCommand

from notifications.services import sync_all_alerts


class Command(BaseCommand):
    help = (
        "Re-check stock and expiry and send any alert repeat that is due "
        "(out-of-stock every 2 hours until restocked). Schedule this from a "
        "Render Cron Job, e.g.  */30 * * * *  python manage.py send_stock_reminders"
    )

    def handle(self, *args, **options):
        sync_all_alerts(force=True)
        self.stdout.write(self.style.SUCCESS("Stock alerts re-checked."))
