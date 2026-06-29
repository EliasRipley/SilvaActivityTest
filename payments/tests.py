from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Site, Activity, Payment, SiteSenior, BookingHold, COMPANY_WIDE_NAME
from .utils import normalize_name


# ── Utility Tests ────────────────────────────────────────────────────────


class NormalizeNameTests(TestCase):
    def test_title_case(self):
        self.assertEqual(normalize_name("john smith"), "John Smith")

    def test_weird_caps(self):
        self.assertEqual(normalize_name("jOhN sMiTh"), "John Smith")

    def test_extra_whitespace(self):
        self.assertEqual(normalize_name("  john   smith  "), "John Smith")

    def test_empty_string(self):
        self.assertEqual(normalize_name(""), "")

    def test_already_normal(self):
        self.assertEqual(normalize_name("Jane Doe"), "Jane Doe")

    def test_mc_names(self):
        self.assertEqual(normalize_name("macdonald"), "Macdonald")


# ── Model Tests ──────────────────────────────────────────────────────────


class SiteModelTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site", slug="test-site", is_active=True
        )

    def test_site_str(self):
        self.assertEqual(str(self.site), "Test Site")

    def test_site_inactive_excluded(self):
        inactive = Site.objects.create(
            name="Inactive", slug="inactive", is_active=False
        )
        self.assertCountEqual(
            Site.objects.filter(is_active=True), [self.site]
        )


class ActivityModelTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(name="S1", slug="s1")
        self.activity = Activity.objects.create(
            site=self.site,
            name="Beach Trip",
            price_pennies=1500,
            start_date="2026-07-15",
        )

    def test_price_pounds(self):
        self.assertEqual(self.activity.price_pounds, 15.00)

    def test_no_capacity_by_default(self):
        self.assertFalse(self.activity.has_capacity)
        self.assertIsNone(self.activity.spaces_remaining)
        self.assertFalse(self.activity.is_full)
        self.assertTrue(self.activity.can_book())

    def test_capacity_available(self):
        self.activity.max_spaces = 5
        self.activity.save()
        self.assertTrue(self.activity.has_capacity)
        self.assertEqual(self.activity.spaces_remaining, 5)
        self.assertFalse(self.activity.is_full)

    def test_capacity_full(self):
        self.activity.max_spaces = 1
        self.activity.save()
        Payment.objects.create(
            activity=self.activity,
            service_user_name="John",
            normalized_name="John",
            amount_pennies=1500,
            status="paid",
            paid_at=timezone.now(),
        )
        self.assertEqual(self.activity.spaces_remaining, 0)
        self.assertTrue(self.activity.is_full)

    def test_capacity_respects_holds(self):
        self.activity.max_spaces = 1
        self.activity.save()
        BookingHold.objects.create(
            activity=self.activity,
            session_key="test-session",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.assertEqual(self.activity.spaces_remaining, 0)
        self.assertTrue(self.activity.is_full)


    def test_company_wide_activity(self):
        cw = Activity.objects.create(
            site=None,
            name="Company Event",
            price_pennies=500,
            start_date="2026-09-01",
        )
        self.assertTrue(cw.is_company_wide)
        self.assertEqual(cw.display_site_name, COMPANY_WIDE_NAME)
        self.assertIn(COMPANY_WIDE_NAME, str(cw))

    def test_site_specific_activity(self):
        self.assertFalse(self.activity.is_company_wide)
        self.assertEqual(self.activity.display_site_name, "S1")

    def test_payment_closes_at_not_set(self):
        self.assertIsNone(self.activity.payment_closes_at)
        self.assertFalse(self.activity.is_payment_closed)
        self.assertTrue(self.activity.can_book())

    def test_payment_closes_at_future(self):
        self.activity.payment_closes_at = date(2099, 12, 31)
        self.activity.save()
        self.assertFalse(self.activity.is_payment_closed)
        self.assertTrue(self.activity.can_book())

    def test_payment_closes_at_today(self):
        self.activity.payment_closes_at = timezone.localdate()
        self.activity.save()
        self.assertTrue(self.activity.is_payment_closed)
        self.assertFalse(self.activity.can_book())

    def test_payment_closes_at_past(self):
        self.activity.payment_closes_at = date(2020, 1, 1)
        self.activity.save()
        self.assertTrue(self.activity.is_payment_closed)
        self.assertFalse(self.activity.can_book())

    def test_payment_closed_overrides_capacity(self):
        self.activity.max_spaces = 5
        self.activity.payment_closes_at = date(2020, 1, 1)
        self.activity.save()
        self.assertFalse(self.activity.can_book())
        self.assertEqual(self.activity.spaces_remaining, 5)


class BookingHoldTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(name="S1", slug="s1")
        self.activity = Activity.objects.create(
            site=self.site,
            name="Zoo Trip",
            price_pennies=2000,
            start_date="2026-08-01",
        )

    def test_create_hold(self):
        hold = BookingHold.create_hold(
            self.activity, "session-1", hold_minutes=10
        )
        self.assertEqual(hold.activity, self.activity)
        self.assertEqual(hold.session_key, "session-1")
        self.assertFalse(hold.is_expired)

    def test_recreate_hold_renews(self):
        hold1 = BookingHold.create_hold(
            self.activity, "session-1", hold_minutes=10
        )
        old_expires = hold1.expires_at
        hold2 = BookingHold.create_hold(
            self.activity, "session-1", hold_minutes=20
        )
        self.assertEqual(hold1.id, hold2.id)
        self.assertGreater(hold2.expires_at, old_expires)

    def test_hold_expiry(self):
        hold = BookingHold.objects.create(
            activity=self.activity,
            session_key="expired-session",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(hold.is_expired)

    def test_release_expired(self):
        BookingHold.objects.create(
            activity=self.activity,
            session_key="expired",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        BookingHold.objects.create(
            activity=self.activity,
            session_key="valid",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        count = BookingHold.release_expired()
        self.assertEqual(count, 1)
        self.assertEqual(BookingHold.objects.count(), 1)


# ── View Tests ───────────────────────────────────────────────────────────


class PublicFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.site = Site.objects.create(name="S1", slug="s1")
        self.activity = Activity.objects.create(
            site=self.site,
            name="Trip",
            price_pennies=1000,
            start_date="2026-07-15",
        )

    def test_home_page_shows_sites(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "S1")

    def test_site_activities_shows_activities(self):
        resp = self.client.get(
            reverse("site_activities", args=["s1"])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Trip")

    def test_site_activities_includes_company_wide(self):
        Activity.objects.create(
            site=None,
            name="All-Sites Event",
            price_pennies=500,
            start_date="2026-09-01",
        )
        resp = self.client.get(
            reverse("site_activities", args=["s1"])
        )
        self.assertContains(resp, "All-Sites Event")

    def test_activity_pay_page(self):
        resp = self.client.get(
            reverse("activity_pay", args=[self.activity.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "person attending")

    def test_full_activity_shows_full_page(self):
        self.activity.max_spaces = 0
        self.activity.save()
        resp = self.client.get(
            reverse("activity_pay", args=[self.activity.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Activity Is Full")

    def test_payment_success_requires_session(self):
        resp = self.client.get(reverse("payment_success"))
        self.assertRedirects(resp, reverse("home"))


class SiteSeniorFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.site = Site.objects.create(name="S1", slug="s1")
        self.user = User.objects.create_user(
            username="senior@test.com",
            email="senior@test.com",
            password="password123",
        )
        SiteSenior.objects.create(user=self.user, site=self.site)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("site_dashboard"))
        self.assertNotEqual(resp.status_code, 200)

    def test_dashboard_shows_site_name(self):
        self.client.login(username="senior@test.com", password="password123")
        resp = self.client.get(reverse("site_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "S1")

    def test_manage_activities(self):
        self.client.login(username="senior@test.com", password="password123")
        resp = self.client.get(reverse("site_manage_activities"))
        self.assertEqual(resp.status_code, 200)

    def test_create_activity(self):
        self.client.login(username="senior@test.com", password="password123")
        resp = self.client.post(
            reverse("site_activity_new"),
            {
                "name": "New Trip",
                "price_pounds": "20.00",
                "start_date": "2026-08-01",
            },
        )
        self.assertRedirects(resp, reverse("site_manage_activities"))
        self.assertEqual(self.site.activities.count(), 1)


class FinanceFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_superuser(
            username="admin@test.com", email="admin@test.com", password="password123"
        )

    def test_finance_requires_staff(self):
        resp = self.client.get(reverse("headoffice_dashboard"))
        self.assertNotEqual(resp.status_code, 200)

    def test_finance_dashboard(self):
        self.client.login(username="admin@test.com", password="password123")
        resp = self.client.get(reverse("headoffice_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Headoffice Dashboard")

    def test_csv_export(self):
        self.client.login(username="admin@test.com", password="password123")
        resp = self.client.get(reverse("headoffice_csv_export"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            resp["Content-Type"].startswith("text/csv")
        )


# ── Capacity Overbooking Prevention ──────────────────────────────────────


class OverbookingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.site = Site.objects.create(name="S1", slug="s1")
        self.activity = Activity.objects.create(
            site=self.site,
            name="Limited Trip",
            price_pennies=1000,
            start_date="2026-07-15",
            max_spaces=1,
        )

    def test_can_book_when_space_available(self):
        self.assertTrue(self.activity.can_book())

    def test_cannot_book_when_full(self):
        Payment.objects.create(
            activity=self.activity,
            service_user_name="John",
            normalized_name="John",
            amount_pennies=1000,
            status="paid",
            paid_at=timezone.now(),
        )
        self.assertFalse(self.activity.can_book())

    def test_hold_prevents_booking(self):
        BookingHold.create_hold(self.activity, "other-session")
        self.assertFalse(self.activity.can_book())

    def test_released_hold_allows_booking(self):
        BookingHold.objects.create(
            activity=self.activity,
            session_key="old-session",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        BookingHold.release_expired()
        self.assertTrue(self.activity.can_book())
