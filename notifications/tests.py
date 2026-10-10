from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from inventory.models import Batch, Category, Medicine
from notifications.models import Notification
from notifications import services
from notifications.services import sync_all_alerts, sync_medicine_alerts

User = get_user_model()


class OutOfStockRepeatTests(APITestCase):
    def setUp(self):
        services._last_sync = 0.0
        self.a = User.objects.create_user("a", "a@x.com", "pass12345")
        self.b = User.objects.create_user("b", "b@x.com", "pass12345")
        cat = Category.objects.create(name="c", description="")
        self.med = Medicine.objects.create(
            name="Amoxicillin", generic_name="x", description="", category=cat,
            sku="AMX", units="caps", reorder_level=10)
        self.batch = Batch.objects.create(
            medicine=self.med, batch_number="B1", quantity=0,
            expiry_date=timezone.localdate() + timedelta(days=400), buying_price=1)

    def out(self, user=None):
        qs = Notification.objects.filter(notification_type="OUT_OF_STOCK", is_resolved=False)
        return qs.filter(receiver=user) if user else qs

    def test_everyone_notified_once(self):
        now = timezone.now()
        sync_medicine_alerts(self.med, now=now)
        sync_medicine_alerts(self.med, now=now + timedelta(minutes=30))
        self.assertEqual(self.out().count(), 2)
        self.assertEqual(self.out(self.a).get().reminder_count, 0)

    def test_repeats_every_two_hours_until_restocked(self):
        now = timezone.now()
        sync_medicine_alerts(self.med, now=now)
        n = self.out(self.a).get()
        Notification.objects.filter(pk=n.pk).update(is_read=True)

        sync_medicine_alerts(self.med, now=now + timedelta(hours=1, minutes=59))
        n.refresh_from_db()
        self.assertEqual((n.reminder_count, n.is_read), (0, True))

        sync_medicine_alerts(self.med, now=now + timedelta(hours=2, minutes=1))
        n.refresh_from_db()
        self.assertEqual((n.reminder_count, n.is_read), (1, False))   # fired again, unread

        sync_medicine_alerts(self.med, now=now + timedelta(hours=4, minutes=5))
        n.refresh_from_db()
        self.assertEqual(n.reminder_count, 2)
        self.assertEqual(self.out(self.a).count(), 1)   # same row, not a pile of duplicates

        self.batch.quantity = 40
        self.batch.save()
        sync_medicine_alerts(self.med, now=now + timedelta(hours=6))
        self.assertEqual(self.out().count(), 0)          # restocked -> stops repeating
        n.refresh_from_db()
        self.assertTrue(n.is_resolved)

    def test_list_endpoint_triggers_sync_and_command_forces_it(self):
        self.client.force_authenticate(self.a)
        r = self.client.get("/api/notifications/")
        self.assertEqual(r.status_code, 200)
        types = [x["notification_type"] for x in r.data["results"]]
        self.assertIn("OUT_OF_STOCK", types)
        self.assertIsNotNone(r.data["results"][0]["medicine"])
        call_command("send_stock_reminders")

    def test_mark_read_and_mark_all(self):
        sync_all_alerts(force=True)
        self.client.force_authenticate(self.a)
        first = self.client.get("/api/notifications/").data["results"][0]["id"]
        self.assertTrue(self.client.patch(f"/api/notifications/{first}/mark-as-read/").data["is_read"])
        self.client.post("/api/notifications/mark-all-read/")
        self.assertFalse(Notification.objects.filter(receiver=self.a, is_read=False).exists())

    def test_expiry_alerts(self):
        self.batch.quantity = 5
        self.batch.expiry_date = timezone.localdate() - timedelta(days=3)
        self.batch.save()
        sync_all_alerts(force=True)
        self.assertTrue(Notification.objects.filter(notification_type="MEDICINE_EXPIRED", batch=self.batch).exists())
        self.batch.expiry_date = timezone.localdate() + timedelta(days=10)
        self.batch.save()
        sync_all_alerts(force=True)
        self.assertFalse(Notification.objects.filter(notification_type="MEDICINE_EXPIRED", is_resolved=False).exists())
        self.assertTrue(Notification.objects.filter(notification_type="MEDICINE_EXPIRING", is_resolved=False).exists())
