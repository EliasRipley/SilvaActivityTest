import csv
import json
import stripe
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q, Sum
from django.views.decorators.csrf import csrf_exempt
from .models import Site, Activity, Payment, SiteSenior, BookingHold
from .forms import ServiceUserForm, ActivityForm
from .utils import normalize_name

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_payment_intent(
    amount_pennies: int,
    description: str,
    activity_id: int,
    service_user_name: str,
) -> dict:
    intent = stripe.PaymentIntent.create(
        amount=amount_pennies,
        currency="gbp",
        description=description,
        metadata={
            "activity_id": str(activity_id),
            "service_user_name": service_user_name,
        },
        automatic_payment_methods={"enabled": True},
    )
    return {
        "client_secret": intent.client_secret,
        "intent_id": intent.id,
    }


def redirect_after_login(request):
    if request.user.is_staff:
        return redirect("headoffice_dashboard")
    if hasattr(request.user, "site_senior"):
        return redirect("site_dashboard")
    return redirect("home")


# ── Booking hold sweeper (run on every public page load) ─────────────────


def _release_expired_holds():
    BookingHold.release_expired()


# ── Public payment flow ──────────────────────────────────────────────────


def home(request):
    _release_expired_holds()
    sites = Site.objects.filter(is_active=True)
    has_company_wide = Activity.objects.filter(
        site__isnull=True, is_active=True
    ).exists()
    return render(
        request,
        "payments/home.html",
        {"sites": sites, "has_company_wide": has_company_wide},
    )


def company_wide_activities(request):
    _release_expired_holds()
    activities = Activity.objects.filter(
        site__isnull=True, is_active=True
    )
    return render(
        request,
        "payments/company_wide_activities.html",
        {"activities": activities},
    )


def site_activities(request, site_slug):
    _release_expired_holds()
    site = get_object_or_404(Site, slug=site_slug, is_active=True)
    activities = site.activities.filter(is_active=True)
    company_wide = Activity.objects.filter(
        site__isnull=True, is_active=True
    )
    all_activities = list(activities) + list(company_wide)
    all_activities.sort(key=lambda a: a.start_date)
    return render(
        request,
        "payments/site_activities.html",
        {"site": site, "activities": all_activities},
    )


def activity_pay(request, activity_id):
    _release_expired_holds()
    activity = get_object_or_404(
        Activity, id=activity_id, is_active=True
    )
    if activity.site and not activity.site.is_active:
        return redirect("home")

    # Check capacity and payment closure upfront
    if not activity.can_book():
        return render(
            request,
            "payments/activity_full.html",
            {"activity": activity},
        )

    if request.method == "POST":
        form = ServiceUserForm(request.POST)
        if form.is_valid():
            raw_name = form.cleaned_data["service_user_name"]
            normalized = normalize_name(raw_name)

            # Double-check capacity before creating hold
            if not activity.can_book():
                if activity.is_payment_closed:
                    msg = "Sorry, payments for this activity are now closed."
                else:
                    msg = "Sorry, this activity is now full."
                messages.error(request, msg)
                if activity.site:
                    return redirect("site_activities", site_slug=activity.site.slug)
                return redirect("company_wide_activities")

            # Create a booking hold (10 min expiry)
            try:
                hold = BookingHold.create_hold(
                    activity,
                    request.session.session_key or request.session._get_or_create_session_key(),
                    hold_minutes=settings.BOOKING_HOLD_MINUTES,
                )
            except Exception:
                pass

            # Store data in session for Stripe callback
            request.session["pending_payment"] = {
                "activity_id": activity.id,
                "service_user_name": raw_name,
                "normalized_name": normalized,
                "amount_pennies": activity.price_pennies,
            }

            try:
                intent_data = create_payment_intent(
                    amount_pennies=activity.price_pennies,
                    description=f"{activity.display_site_name} – {activity.name} – {raw_name}",
                    activity_id=activity.id,
                    service_user_name=raw_name,
                )
                request.session["stripe_intent_id"] = intent_data["intent_id"]
                return render(
                    request,
                    "payments/payment_card.html",
                    {
                        "activity": activity,
                        "client_secret": intent_data["client_secret"],
                        "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
                        "service_user_name": raw_name,
                    },
                )
            except Exception as e:
                messages.error(
                    request,
                    "Something went wrong with payment setup. Please try again.",
                )
                return redirect("activity_pay", activity_id=activity.id)
    else:
        form = ServiceUserForm()

    return render(
        request,
        "payments/activity_pay.html",
        {"activity": activity, "form": form},
    )


def _is_stripe_test_mode():
    return settings.STRIPE_SECRET_KEY.startswith("sk_test_")


def _record_payment(activity_id, service_user_name, stripe_payment_intent_id, amount_pennies, is_test=None):
    """Create a Payment record if one doesn't already exist for this intent."""
    if Payment.objects.filter(stripe_payment_intent_id=stripe_payment_intent_id).exists():
        return None
    activity = Activity.objects.get(id=activity_id)
    normalized = normalize_name(service_user_name)
    if is_test is None:
        is_test = _is_stripe_test_mode()
    return Payment.objects.create(
        activity=activity,
        service_user_name=service_user_name,
        normalized_name=normalized,
        amount_pennies=amount_pennies,
        stripe_payment_intent_id=stripe_payment_intent_id,
        is_test=is_test,
        status="paid",
        paid_at=timezone.now(),
    )


def payment_success(request):
    _release_expired_holds()
    pending = request.session.pop("pending_payment", None)
    intent_id = request.session.pop("stripe_intent_id", "")

    if pending:
        # Normal flow — session data intact
        activity = Activity.objects.get(id=pending["activity_id"])
        _record_payment(
            activity_id=pending["activity_id"],
            service_user_name=pending["service_user_name"],
            stripe_payment_intent_id=intent_id,
            amount_pennies=pending["amount_pennies"],
        )
        name = pending["normalized_name"]
        session_key = request.session.session_key
        if session_key:
            BookingHold.objects.filter(
                activity=activity, session_key=session_key
            ).delete()
    else:
        # Session was lost — recover from Stripe API using URL query param
        pi_id = request.GET.get("payment_intent")
        if not pi_id:
            return redirect("home")
        try:
            intent = stripe.PaymentIntent.retrieve(pi_id)
        except stripe.error.StripeError:
            return redirect("home")
        if intent.status != "succeeded":
            return redirect("home")
        metadata = intent.metadata or {}
        if not metadata.get("activity_id"):
            return redirect("home")
        payment = _record_payment(
            activity_id=int(metadata["activity_id"]),
            service_user_name=metadata.get("service_user_name", ""),
            stripe_payment_intent_id=pi_id,
            amount_pennies=intent.amount_received or intent.amount,
            is_test=not intent.livemode,
        )
        if payment is None:
            payment = Payment.objects.get(stripe_payment_intent_id=pi_id)
        name = payment.normalized_name

    return render(
        request,
        "payments/payment_success.html",
        {"name": name},
    )


def payment_cancelled(request):
    _release_expired_holds()
    pending = request.session.pop("pending_payment", None)
    request.session.pop("stripe_intent_id", None)

    # Release hold
    if pending:
        session_key = request.session.session_key
        if session_key:
            BookingHold.objects.filter(
                activity_id=pending["activity_id"],
                session_key=session_key,
            ).delete()

    messages.info(request, "Payment was cancelled.")
    return redirect("home")


# ── Stripe webhook ───────────────────────────────────────────────────────


@csrf_exempt
def stripe_webhook(request):
    """Receive Stripe webhook events (e.g. payment_intent.succeeded)."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if endpoint_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=400)
    else:
        # No secret configured — parse payload directly for development
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

    if event.get("type") == "payment_intent.succeeded":
        intent = event["data"]["object"]
        metadata = intent.get("metadata", {})
        pi_id = intent["id"]

        if metadata.get("activity_id") and not Payment.objects.filter(
            stripe_payment_intent_id=pi_id
        ).exists():
            try:
                _record_payment(
                    activity_id=int(metadata["activity_id"]),
                    service_user_name=metadata.get("service_user_name", ""),
                    stripe_payment_intent_id=pi_id,
                    amount_pennies=intent.get("amount_received")
                    or intent.get("amount", 0),
                    is_test=not intent.get("livemode", False),
                )
            except Activity.DoesNotExist:
                return HttpResponse(status=200)

    return HttpResponse(status=200)


# ── Site Senior Views ────────────────────────────────────────────────────


def is_site_senior(user):
    return hasattr(user, "site_senior")


@login_required
@user_passes_test(is_site_senior)
def site_dashboard(request):
    _release_expired_holds()
    senior = request.user.site_senior
    site = senior.site

    activities = list(site.activities.all())
    company_wide = list(Activity.objects.filter(site__isnull=True))
    all_activities = activities + company_wide
    all_activities.sort(key=lambda a: a.start_date or a.created_at)

    activity_data = []
    for a in all_activities:
        paid_count = a.payments.filter(status="paid").count()
        total_paid = (
            a.payments.filter(status="paid").aggregate(s=Sum("amount_pennies"))["s"]
            or 0
        )
        activity_data.append(
            {
                "activity": a,
                "paid_count": paid_count,
                "total_paid_pounds": total_paid / 100,
                "spaces_remaining": a.spaces_remaining,
            }
        )

    all_payments = (
        Payment.objects.filter(
            Q(activity__site=site) | Q(activity__site__isnull=True),
            status="paid",
        )
        .select_related("activity__site")
        .order_by("-paid_at")[:50]
    )

    total_paid_pounds = (
        Payment.objects.filter(
            Q(activity__site=site) | Q(activity__site__isnull=True),
            status="paid",
        ).aggregate(s=Sum("amount_pennies"))["s"]
        or 0
    ) / 100

    return render(
        request,
        "payments/site_dashboard.html",
        {
            "site": site,
            "activity_data": activity_data,
            "recent_payments": all_payments,
            "total_paid_pounds": total_paid_pounds,
        },
    )


@login_required
@user_passes_test(is_site_senior)
def site_manage_activities(request):
    senior = request.user.site_senior
    site = senior.site
    activities = site.activities.all()
    company_wide = Activity.objects.filter(site__isnull=True)

    return render(
        request,
        "payments/manage_activities.html",
        {
            "site": site,
            "activities": activities,
            "company_wide_activities": company_wide,
        },
    )


@login_required
@user_passes_test(is_site_senior)
def site_activity_edit(request, activity_id=None):
    senior = request.user.site_senior
    site = senior.site

    if activity_id:
        activity = get_object_or_404(
            Activity,
            Q(id=activity_id) & (Q(site=site) | Q(site__isnull=True)),
        )
    else:
        activity = None

    if request.method == "POST":
        form = ActivityForm(request.POST, instance=activity)
        if form.is_valid():
            obj = form.save(commit=False)
            if form.cleaned_data.get("is_silva_care_wide"):
                obj.site = None
            else:
                obj.site = site
            obj.save()
            messages.success(
                request,
                f"Activity '{obj.name}' saved successfully.",
            )
            return redirect("site_manage_activities")
    else:
        form = ActivityForm(instance=activity)

    return render(
        request,
        "payments/activity_form.html",
        {"form": form, "activity": activity, "site": site},
    )


@login_required
@user_passes_test(is_site_senior)
def site_activity_delete(request, activity_id):
    senior = request.user.site_senior
    activity = get_object_or_404(
        Activity,
        Q(id=activity_id) & (Q(site=senior.site) | Q(site__isnull=True)),
    )

    if activity.payments.exists():
        messages.error(
            request,
            "Cannot delete an activity that has payments. Deactivate it instead.",
        )
        return redirect("site_manage_activities")

    activity.delete()
    messages.success(request, "Activity deleted.")
    return redirect("site_manage_activities")


@login_required
@user_passes_test(is_site_senior)
def site_payments_view(request):
    senior = request.user.site_senior
    site = senior.site
    payments = (
        Payment.objects.filter(
            Q(activity__site=site) | Q(activity__site__isnull=True)
        )
        .select_related("activity__site")
        .order_by("-created_at")
    )

    return render(
        request,
        "payments/site_payments.html",
        {"site": site, "payments": payments},
    )





