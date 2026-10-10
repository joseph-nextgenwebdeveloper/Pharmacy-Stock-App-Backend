from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from inventory.models import Category, Medicine
from inventory.services import create_batch_with_stock

User = get_user_model()


class DashboardTests(APITestCase):
    def test_dashboard_numbers(self):
        u = User.objects.create_user("c", "c@x.com", "pass12345")
        self.client.force_authenticate(u)
        cat = Category.objects.create(name="c", description="")
        med = Medicine.objects.create(name="P", generic_name="p", description="", category=cat, sku="P", units="t", reorder_level=5)
        create_batch_with_stock(user=u, medicine=med, batch_number="B", expiry_date=timezone.localdate() + timedelta(days=10), quantity=50, buying_price=1)
        d = self.client.get("/api/dashboard/").data
        self.assertEqual((d["total_stock"], d["today_received"], d["expiring_batches"], d["my_updates_today"]), (50, 50, 1, 1))
        self.assertEqual(len(d["weekly_movements"]), 7)
        self.assertEqual(d["weekly_movements"][-1]["units_in"], 50)
