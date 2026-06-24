import re
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone


class CaseInsensitiveAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None:
            return None
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


class Site(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


COMPANY_WIDE_NAME = "Silva Care Wide"


class Activity(models.Model):
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="activities",
        null=True,
        blank=True,
        help_text="Leave blank to make this activity available across all sites.",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price_pennies = models.IntegerField(
        help_text="Price stored in pence (e.g. £10.50 = 1050)"
    )
    start_date = models.DateField()
    max_spaces = models.IntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for unlimited spaces",
    )
    payment_closes_at = models.DateField(
        null=True,
        blank=True,
        help_text="Optional closing date – payments will not be accepted on or after this date.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["site", "start_date"]
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.display_site_name} – {self.name}"

    @property
    def display_site_name(self):
        return self.site.name if self.site else COMPANY_WIDE_NAME

    @property
    def is_company_wide(self):
        return self.site is None

    @property
    def price_pounds(self):
        return self.price_pennies / 100

    @property
    def has_capacity(self):
        """Whether this activity has a space limit configured."""
        return self.max_spaces is not None

    @property
    def spaces_remaining(self):
        if self.max_spaces is None:
            return None
        confirmed = (
            self.payments.filter(status="paid").count()
        )
        held = BookingHold.objects.filter(
            activity=self, expires_at__gt=timezone.now()
        ).count()
        return self.max_spaces - confirmed - held

    @property
    def is_full(self):
        if self.max_spaces is None:
            return False
        return self.spaces_remaining <= 0

    @property
    def is_payment_closed(self):
        if self.payment_closes_at is None:
            return False
        from django.utils.timezone import localdate
        return localdate() >= self.payment_closes_at

    def can_book(self):
        if self.is_payment_closed:
            return False
        if self.max_spaces is None:
            return True
        return self.spaces_remaining > 0


class BookingHold(models.Model):
    """Temporary hold on a space while someone is paying."""
    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name="holds"
    )
    session_key = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = [("activity", "session_key")]

    def __str__(self):
        return f"Hold on {self.activity} until {self.expires_at}"

    @classmethod
    def create_hold(cls, activity, session_key, hold_minutes=10):
        now = timezone.now()
        expires = now + timezone.timedelta(minutes=hold_minutes)
        hold, created = cls.objects.get_or_create(
            activity=activity,
            session_key=session_key,
            defaults={"expires_at": expires},
        )
        if not created:
            hold.expires_at = expires
            hold.save()
        return hold

    @classmethod
    def release_expired(cls):
        """Sweeper: release all expired holds."""
        count, _ = cls.objects.filter(
            expires_at__lte=timezone.now()
        ).delete()
        return count

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    activity = models.ForeignKey(
        Activity, on_delete=models.CASCADE, related_name="payments"
    )
    service_user_name = models.CharField(max_length=300)
    normalized_name = models.CharField(max_length=300, blank=True)
    amount_pennies = models.IntegerField()
    stripe_payment_intent_id = models.CharField(
        max_length=300, blank=True
    )
    is_test = models.BooleanField(
        default=True,
        help_text="Whether this payment was made in Stripe test mode",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.service_user_name} \u2013 {self.activity.name} ({self.status})"

    @property
    def amount_pounds(self):
        return self.amount_pennies / 100


class SiteSenior(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="site_senior"
    )
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name="seniors"
    )

    def __str__(self):
        return f"{self.user.get_full_name()} @ {self.site.name}"
