from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import ActivityLog
from inventory.models import Batch, Category, Medicine, StockMovement
from notifications.models import Notification

User = get_user_model()


class InventoryBase(APITestCase):
    def setUp(self):
        self.clerk = User.objects.create_user(
            "clerk", "clerk@x.com", "pass12345", first_name="Jane", last_name="Otieno",
            role="STOCK_CLERK",
        )
        self.pharm = User.objects.create_user(
            "pharm", "pharm@x.com", "pass12345", role="PHARMACIST"
        )
        self.cat = Category.objects.create(name="Analgesics", description="")
        self.med = Medicine.objects.create(
            name="Paracetamol 500mg", generic_name="Paracetamol", description="",
            category=self.cat, sku="PAR-500", barcode="4901234567890",
            units="tabs", reorder_level=20,
        )
        self.client.force_authenticate(self.clerk)

    def new_batch(self, number="PAR-001", qty=100, days=365, **extra):
        body = {
            "medicine": self.med.id, "batch_number": number,
            "expiry_date": str(timezone.localdate() + timedelta(days=days)),
            "quantity": qty, "buying_price": "5.00", "selling_price": "8.00",
        }
        body.update(extra)
        return self.client.post("/api/inventory/batches/", body, format="json")


class BatchTests(InventoryBase):
    def test_create_batch_books_opening_stock_in_ledger(self):
        r = self.new_batch(qty=500)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["quantity"], 500)
        self.assertEqual(r.data["original_quantity"], 500)
        self.assertEqual(r.data["status"], "ACTIVE")
        m = StockMovement.objects.get()
        self.assertEqual((m.movement_type, m.reason, m.quantity), ("IN", "RECEIVED", 500))
        self.assertEqual((m.quantity_before, m.quantity_after), (0, 500))
        self.assertEqual(m.performed_by, self.clerk)
        log = ActivityLog.objects.get(action="STOCK_IN")
        self.assertEqual(log.user, self.clerk)
        self.assertEqual(log.quantity, 500)
        self.assertIn("new batch PAR-001", log.summary)

    def test_one_medicine_many_batches_and_total(self):
        self.new_batch("PAR-001", 500)
        self.new_batch("PAR-002", 300, days=700)
        r = self.client.get(f"/api/inventory/medicines/{self.med.id}/")
        self.assertEqual(r.data["quantity"], 800)

    def test_duplicate_lot_number_same_medicine_rejected(self):
        self.new_batch("PAR-001")
        r = self.new_batch("PAR-001")
        self.assertEqual(r.status_code, 400)

    def test_quantity_cannot_be_edited_after_creation(self):
        b = self.new_batch(qty=50).data
        r = self.client.patch(f"/api/inventory/batches/{b['id']}/", {"quantity": 9999}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Batch.objects.get(pk=b["id"]).quantity, 50)

    def test_status_filter_and_search(self):
        self.new_batch("A", 10)
        Batch.objects.create(medicine=self.med, batch_number="OLD", quantity=5,
                             expiry_date=date(2020, 1, 1), buying_price=1)
        Batch.objects.create(medicine=self.med, batch_number="ZERO", quantity=0,
                             expiry_date=date(2030, 1, 1), buying_price=1)
        def nums(q):
            return sorted(x["batch_number"] for x in self.client.get("/api/inventory/batches/" + q).data["results"])
        self.assertEqual(nums("?status=ACTIVE"), ["A"])
        self.assertEqual(nums("?status=EXPIRED"), ["OLD"])
        self.assertEqual(nums("?status=DEPLETED"), ["ZERO"])
        self.assertEqual(nums("?search=paracetamol"), ["A", "OLD", "ZERO"])

    def test_batch_with_history_cannot_be_deleted(self):
        b = self.new_batch().data
        r = self.client.delete(f"/api/inventory/batches/{b['id']}/")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Batch.objects.filter(pk=b["id"]).exists())

    def test_medicine_with_history_cannot_be_deleted(self):
        self.new_batch()
        r = self.client.delete(f"/api/inventory/medicines/{self.med.id}/")
        self.assertEqual(r.status_code, 400)


class MovementTests(InventoryBase):
    def move(self, batch, qty, kind="OUT", **extra):
        body = {"medicine": self.med.id, "batch": batch, "quantity": qty, "movement_type": kind}
        body.update(extra)
        return self.client.post("/api/inventory/stock-movements/", body, format="json")

    def test_dispense_reduces_stock_and_records_who(self):
        b = self.new_batch(qty=100).data["id"]
        self.client.force_authenticate(self.pharm)
        r = self.move(b, 30)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["reason"], "DISPENSED")
        self.assertEqual(r.data["performed_by"], self.pharm.id)
        self.assertEqual((r.data["quantity_before"], r.data["quantity_after"]), (100, 70))
        self.assertEqual(r.data["performed_by_role"], "PHARMACIST")
        self.assertEqual(Batch.objects.get(pk=b).quantity, 70)

    def test_cannot_go_negative(self):
        b = self.new_batch(qty=5).data["id"]
        r = self.move(b, 8)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Batch.objects.get(pk=b).quantity, 5)
        self.assertEqual(StockMovement.objects.filter(movement_type="OUT").count(), 0)

    def test_expired_cannot_be_dispensed_but_can_be_written_off(self):
        batch = Batch.objects.create(medicine=self.med, batch_number="EXP", quantity=10,
                                     expiry_date=date(2020, 1, 1), buying_price=1)
        r = self.move(batch.id, 2)
        self.assertEqual(r.status_code, 400)
        r = self.move(batch.id, 10, reason="EXPIRED")
        self.assertEqual(r.status_code, 201, r.data)
        batch.refresh_from_db()
        self.assertEqual(batch.quantity, 0)

    def test_reason_must_match_direction(self):
        b = self.new_batch().data["id"]
        self.assertEqual(self.move(b, 1, "IN", reason="DISPENSED").status_code, 400)
        self.assertEqual(self.move(b, 1, "OUT", reason="RECEIVED").status_code, 400)
        self.assertEqual(self.move(b, 3, "OUT", reason="DAMAGED", note="dropped").status_code, 201)

    def test_zero_quantity_rejected(self):
        b = self.new_batch().data["id"]
        self.assertEqual(self.move(b, 0).status_code, 400)

    def test_ledger_is_append_only(self):
        b = self.new_batch().data["id"]
        mid = self.move(b, 1).data["id"]
        self.assertEqual(self.client.delete(f"/api/inventory/stock-movements/{mid}/").status_code, 405)
        self.assertEqual(self.client.patch(f"/api/inventory/stock-movements/{mid}/", {"quantity": 9}, format="json").status_code, 405)

    def test_filters_mine_date_and_search(self):
        b = self.new_batch(qty=100).data["id"]
        self.client.force_authenticate(self.pharm)
        self.move(b, 5)
        self.client.force_authenticate(self.clerk)
        mine = self.client.get("/api/inventory/stock-movements/?performed_by=me").data["results"]
        self.assertEqual({m["performed_by"] for m in mine}, {self.clerk.id})
        today = str(timezone.localdate())
        self.assertEqual(self.client.get(f"/api/inventory/stock-movements/?date={today}").data["count"], 2)
        self.assertEqual(self.client.get("/api/inventory/stock-movements/?search=pharm").data["count"], 1)
        self.assertEqual(self.client.get("/api/inventory/stock-movements/?page_size=1").data["results"].__len__(), 1)

    def test_alerts_follow_stock(self):
        b = self.new_batch(qty=25).data["id"]
        self.move(b, 10)   # 15 <= reorder 20 -> low
        self.assertTrue(Notification.objects.filter(notification_type="LOW_STOCK", receiver=self.pharm, is_resolved=False).exists())
        self.move(b, 15)   # 0 -> out
        out = Notification.objects.filter(notification_type="OUT_OF_STOCK", is_resolved=False)
        self.assertEqual(out.count(), 2)  # every active staff member
        self.assertFalse(Notification.objects.filter(notification_type="LOW_STOCK", is_resolved=False).exists())
        self.move(b, 50, "IN")  # restock
        self.assertFalse(Notification.objects.filter(notification_type="OUT_OF_STOCK", is_resolved=False).exists())


class MedicineAuditTests(InventoryBase):
    def test_edit_is_logged_with_diff(self):
        r = self.client.patch(f"/api/inventory/medicines/{self.med.id}/", {"reorder_level": 40}, format="json")
        self.assertEqual(r.status_code, 200)
        log = ActivityLog.objects.get(action="MEDICINE_UPDATED")
        self.assertEqual(log.changes["reorder_level"], {"from": 20, "to": 40})
        self.assertEqual(log.user, self.clerk)
