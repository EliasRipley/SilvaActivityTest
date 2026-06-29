import stripe
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from .models import Activity, Payment, Wallet, WalletTransaction, BookingHold, AppSetting
from .forms import ServiceUserFormForAccount, TopUpForm
from .utils import normalize_name
from .views import create_payment_intent, _release_expired_holds, _is_stripe_test_mode, _su_accounts_enabled, _wallet_system_enabled, _get_max_deposit

stripe.api_key = settings.STRIPE_SECRET_KEY


def is_account_holder(user):
    return hasattr(user, "wallet") and not user.is_staff and not hasattr(user, "site_senior")


@login_required
def account_dashboard(request):
    if not is_account_holder(request.user):
        messages.error(request, "Access denied.")
        return redirect("home")

    if not _su_accounts_enabled():
        messages.error(request, "Service user accounts are currently disabled.")
        return redirect("home")

    _release_expired_holds()
    wallet = request.user.wallet
    service_users = request.user.service_users.filter(is_active=True)

    recent_payments = (
        Payment.objects.filter(paid_by=request.user)
        .select_related("activity__site")
        .order_by("-paid_at")[:10]
    )

    wallet_enabled = _wallet_system_enabled()

    context = {
        "wallet": wallet,
        "service_users": service_users,
        "recent_payments": recent_payments,
        "wallet_enabled": wallet_enabled,
    }

    if wallet_enabled:
        context["transactions"] = wallet.transactions.all()[:50]

    return render(
        request,
        "payments/account/dashboard.html",
        context,
    )


@login_required
def account_balance(request):
    return redirect("account_dashboard")


@login_required
def account_topup(request):
    if not is_account_holder(request.user):
        messages.error(request, "Access denied.")
        return redirect("home")

    if not _wallet_system_enabled():
        messages.info(request, "The wallet system is currently disabled.")
        return redirect("account_dashboard")

    wallet = request.user.wallet

    max_deposit = _get_max_deposit()

    if request.method == "POST":
        form = TopUpForm(request.POST, max_deposit=max_deposit)
        if form.is_valid():
            amount_pounds = form.cleaned_data["amount_pounds"]
            amount_pennies = int(amount_pounds * 100)

            try:
                intent_data = create_payment_intent(
                    amount_pennies=amount_pennies,
                    description=f"Silva Care wallet top-up – {request.user.get_full_name() or request.user.username}",
                    activity_id=0,
                    service_user_name="Wallet Top-Up",
                )
                request.session["topup_intent_id"] = intent_data["intent_id"]
                request.session["topup_amount_pennies"] = amount_pennies
                return render(
                    request,
                    "payments/account/topup_card.html",
                    {
                        "client_secret": intent_data["client_secret"],
                        "stripe_public_key": settings.STRIPE_PUBLIC_KEY,
                        "amount_pounds": amount_pounds,
                    },
                )
            except Exception as e:
                messages.error(
                    request,
                    "Something went wrong. Please try again.",
                )
                return redirect("account_topup")
    else:
        form = TopUpForm(max_deposit=max_deposit)

    return render(
        request,
        "payments/account/topup.html",
        {"form": form, "wallet": wallet, "max_deposit": max_deposit},
    )


@login_required
def account_topup_success(request):
    if not is_account_holder(request.user):
        return redirect("home")

    wallet = request.user.wallet
    intent_id = request.session.pop("topup_intent_id", "")
    amount_pennies = request.session.pop("topup_amount_pennies", 0)
    pi_id = request.GET.get("payment_intent", intent_id)

    if not pi_id:
        messages.error(request, "No payment information found.")
        return redirect("account_dashboard")

    # Check if already processed
    if WalletTransaction.objects.filter(
        stripe_payment_intent_id=pi_id, transaction_type="topup"
    ).exists():
        messages.success(request, "Your balance has been updated.")
        return redirect("account_dashboard")

    if not amount_pennies:
        try:
            intent = stripe.PaymentIntent.retrieve(pi_id)
            if intent.status != "succeeded":
                messages.error(request, "Payment was not successful.")
                return redirect("account_topup")
            amount_pennies = intent.amount_received or intent.amount
        except stripe.error.StripeError:
            messages.error(request, "Could not verify payment.")
            return redirect("account_topup")

    wallet.balance_pennies += amount_pennies
    wallet.save()

    WalletTransaction.objects.create(
        wallet=wallet,
        amount_pennies=amount_pennies,
        transaction_type="topup",
        description="Wallet top-up via card",
        stripe_payment_intent_id=pi_id,
    )

    messages.success(
        request,
        f"£{amount_pennies / 100:.2f} has been added to your balance.",
    )
    return redirect("account_dashboard")


@login_required
def account_topup_cancelled(request):
    request.session.pop("topup_intent_id", None)
    request.session.pop("topup_amount_pennies", None)
    messages.info(request, "Top-up was cancelled.")
    return redirect("account_dashboard")
