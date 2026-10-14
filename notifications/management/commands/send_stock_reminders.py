from django.core.management.base import BaseCommand

from notifications.services import sync_all_alerts


class Command(BaseCommand):
    help = (
        "Re-check stock and expiry and send any alert repeat that is due "
        "(once a day until fixed). Schedule this from a Render Cron Job, "
        "e.g.  0 5 * * *  python manage.py send_stock_reminders  (08:00 Nairobi)"
    )

    def handle(self, *args, **options):
        sync_all_alerts(force=True)
        self.stdout.write(self.style.SUCCESS("Stock alerts re-checked."))
