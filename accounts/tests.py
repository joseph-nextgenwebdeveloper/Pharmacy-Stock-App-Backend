import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import ActivityLog
from accounts.audit import log_activity

User = get_user_model()
TMP = tempfile.mkdtemp()


def png():
    buf = BytesIO()
    Image.new("RGB", (8, 8), "green").save(buf, "PNG")
    return SimpleUploadedFile("me.png", buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TMP)
class AccountTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.clerk = User.objects.create_user("clerk", "c@x.com", "pass12345", role="STOCK_CLERK", first_name="Jane")
        self.manager = User.objects.create_user("mgr", "m@x.com", "pass12345", role="STORE_MANAGER")

    def test_login_is_logged_and_returns_avatar_key(self):
        r = self.client.post("/api/accounts/login/", {"email": "c@x.com", "password": "pass12345"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("avatar", r.data)
        self.assertTrue(ActivityLog.objects.filter(user=self.clerk, action="LOGIN").exists())

    def test_profile_update_with_photo_and_remove(self):
        self.client.force_authenticate(self.clerk)
        r = self.client.patch("/api/accounts/profile/", {"first_name": "Janet", "phone_number": "0712345678", "avatar": png()}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["avatar"].endswith(".png") or "avatars/" in r.data["avatar"])
        self.assertEqual(r.data["first_name"], "Janet")
        log = ActivityLog.objects.get(action="PROFILE_UPDATED")
        self.assertEqual(log.changes["first_name"], {"from": "Jane", "to": "Janet"})
        r = self.client.patch("/api/accounts/profile/", {"remove_avatar": "true"}, format="multipart")
        self.assertIsNone(r.data["avatar"])

    def test_role_and_email_are_read_only(self):
        self.client.force_authenticate(self.clerk)
        self.client.patch("/api/accounts/profile/", {"role": "ADMIN", "email": "z@z.com"}, format="json")
        self.clerk.refresh_from_db()
        self.assertEqual((self.clerk.role, self.clerk.email), ("STOCK_CLERK", "c@x.com"))

    def test_phone_unique(self):
        User.objects.create_user("o", "o@x.com", "pass12345", phone_number="0700000000")
        self.client.force_authenticate(self.clerk)
        r = self.client.patch("/api/accounts/profile/", {"phone_number": "0700000000"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_activity_scoping(self):
        log_activity(self.clerk, "STOCK_IN", "Received 10", quantity=10)
        log_activity(self.manager, "STOCK_OUT", "Dispensed 4", quantity=-4)
        self.client.force_authenticate(self.clerk)
        mine = self.client.get("/api/accounts/activity/").data["results"]
        self.assertEqual({x["user"] for x in mine}, {self.clerk.id})
        self.assertEqual(self.client.get("/api/accounts/activity/?scope=all").status_code, 403)
        self.assertEqual(self.client.get(f"/api/accounts/activity/?user={self.manager.id}").status_code, 403)
        self.assertEqual(self.client.get("/api/accounts/staff/").status_code, 403)
        self.client.force_authenticate(self.manager)
        everyone = self.client.get("/api/accounts/activity/?scope=all").data["results"]
        self.assertEqual({x["user"] for x in everyone}, {self.clerk.id, self.manager.id})
        one = self.client.get(f"/api/accounts/activity/?user={self.clerk.id}").data["results"]
        self.assertEqual({x["user"] for x in one}, {self.clerk.id})
        self.assertEqual(len(self.client.get("/api/accounts/staff/").data), 2)

    def test_summary(self):
        log_activity(self.clerk, "STOCK_IN", "Received 120", quantity=120)
        log_activity(self.clerk, "STOCK_OUT", "Dispensed 24", quantity=-24)
        log_activity(self.clerk, "LOGIN", "Signed in")
        self.client.force_authenticate(self.clerk)
        d = self.client.get("/api/accounts/activity/summary/").data
        self.assertEqual((d["updates_today"], d["net_units_today"], d["units_in_today"], d["units_out_today"]), (2, 96, 120, 24))
        self.assertEqual(self.client.get(f"/api/accounts/activity/summary/?user={self.manager.id}").status_code, 403)
