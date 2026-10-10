from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import ActivityLog
from inventory.models import Batch, Category, Medicine, StockMovement
from suppliers.models import Supplier

User = get_user_model()


class DeliveryAndSaleTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("c", "c@x.com", "pass12345", role="STOCK_CLERK")
        self.client.force_authenticate(self.user)
        cat = Category.objects.create(name="c", description="")
        self.m1 = Medicine.objects.create(name="Paracetamol", generic_name="p", description="", category=cat, sku="P", units="t", reorder_level=5)
        self.m2 = Medicine.objects.create(name="Ibuprofen", generic_name="i", description="", category=cat, sku="I", units="t", reorder_level=5)
        self.sup = Supplier.objects.create(name="MedSupply", company_name="MS", contact_person="Z", phone_number="0700000000")

    def item(self, med, lot, qty):
        return {"medicine": med.id, "batch_number": lot, "expiry_date": str(timezone.localdate() + timedelta(days=300)),
                "quantity": qty, "buying_price": "4.00", "selling_price": "6.00"}

    def test_delivery_makes_one_batch_per_line_with_ledger(self):
        r = self.client.post("/api/purchases/goods-received/", {
            "supplier": self.sup.id, "invoice_number": "INV-9",
            "items": [self.item(self.m1, "P-1", 100), self.item(self.m2, "I-1", 40)]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["supplier_name"], "MedSupply")
        self.assertEqual(Batch.objects.count(), 2)
        self.assertEqual(Batch.objects.get(batch_number="P-1").supplier, self.sup)
        moves = StockMovement.objects.all()
        self.assertEqual(moves.count(), 2)
        self.assertTrue(all(m.reference.startswith("GRN-") and m.performed_by == self.user for m in moves))
        self.assertEqual(ActivityLog.objects.filter(action="STOCK_IN").count(), 2)
        self.assertTrue(ActivityLog.objects.filter(action="GOODS_RECEIVED").exists())
        # header row is not counted as an extra "update"
        s = self.client.get("/api/accounts/activity/summary/").data
        self.assertEqual((s["updates_today"], s["net_units_today"]), (2, 140))

    def test_delivery_with_bad_line_is_all_or_nothing(self):
        Batch.objects.create(medicine=self.m1, batch_number="DUP", quantity=1, expiry_date=timezone.localdate(), buying_price=1)
        before = StockMovement.objects.count()
        try:
            r = self.client.post("/api/purchases/goods-received/", {
                "supplier": self.sup.id,
                "items": [self.item(self.m2, "OK-1", 5), self.item(self.m1, "DUP", 5)]}, format="json")
            self.assertGreaterEqual(r.status_code, 400)
        except Exception:
            pass
        self.assertEqual(Batch.objects.filter(batch_number="OK-1").count(), 0)
        self.assertEqual(StockMovement.objects.count(), before)

    def test_sale_goes_through_ledger_and_blocks_expired(self):
        good = Batch.objects.create(medicine=self.m1, batch_number="G", quantity=10, expiry_date=timezone.localdate() + timedelta(days=90), buying_price=1)
        old = Batch.objects.create(medicine=self.m2, batch_number="O", quantity=10, expiry_date=timezone.localdate() - timedelta(days=1), buying_price=1)
        body = lambda b, m: {"receipt_number": "R-1", "payment_method": "CASH",
                             "items": [{"medicine": m.id, "batch": b.id, "quantity": 4, "unit_price": "10.00"}]}
        self.assertEqual(self.client.post("/api/sales/", body(old, self.m2), format="json").status_code, 400)
        r = self.client.post("/api/sales/", body(good, self.m1), format="json")
        self.assertEqual(r.status_code, 201, r.data)
        good.refresh_from_db()
        self.assertEqual(good.quantity, 6)
        m = StockMovement.objects.get()
        self.assertEqual((m.reason, m.reference, m.quantity_before, m.quantity_after), ("DISPENSED", "R-1", 10, 6))
        self.assertEqual(r.data["items"][0]["medicine_name"], "Paracetamol")
