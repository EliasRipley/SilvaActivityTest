import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count
from payments.models import (
    Site, Activity, Payment, SiteSenior, ServiceUser,
    Wallet, WalletTransaction, AppSetting, COMPANY_WIDE_NAME,
)
from payments.forms import HeadofficeActivityForm, AccountHolderUserForm, AccountHolderEditForm


def is_staff(user):
    return user.is_staff


# ── Dashboard ────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def dashboard(request):
    total_sites = Site.objects.count()
    total_activities = Activity.objects.count()
    total_seniors = SiteSenior.objects.count()
    total_account_holders = User.objects.filter(
        wallet__isnull=False, is_staff=False
    ).exclude(site_senior__isnull=False).count()
    total_paid = (
        Payment.objects.filter(status="paid").aggregate(s=Sum("amount_pennies"))["s"]
        or 0
    )
    payment_count = Payment.objects.filter(status="paid").count()
    recent_payments = (
        Payment.objects.filter(status="paid")
        .select_related("activity__site")
        .order_by("-paid_at")[:10]
    )

    recent_topups = (
        WalletTransaction.objects.filter(transaction_type="topup")
        .select_related("wallet__user")
        .order_by("-created_at")[:10]
    )

    payments_by_site = (
        Payment.objects.filter(status="paid")
        .values("activity__site__name")
        .annotate(total_pennies=Sum("amount_pennies"), count=Count("id"))
        .order_by("-total_pennies")
    )
    payments_by_site = [
        {"name": p["activity__site__name"] or COMPANY_WIDE_NAME, "total_pounds": p["total_pennies"] / 100, "count": p["count"]}
        for p in payments_by_site
    ]

    now = timezone.now()

    return render(
        request,
        "payments/headoffice/dashboard.html",
        {
            "total_sites": total_sites,
            "total_activities": total_activities,
            "total_seniors": total_seniors,
            "total_account_holders": total_account_holders,
            "total_paid_pounds": total_paid / 100,
            "payment_count": payment_count,
            "recent_payments": recent_payments,
            "recent_topups": recent_topups,
            "payments_by_site": payments_by_site,
            "current_year": now.year,
        },
    )


# ── Sites ────────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def sites_list(request):
    sites = Site.objects.all()
    site_data = []
    for s in sites:
        site_data.append(
            {
                "site": s,
                "activity_count": s.activities.count(),
                "senior_count": s.seniors.count(),
                "payment_count": Payment.objects.filter(
                    activity__site=s, status="paid"
                ).count(),
                "total_paid": (
                    Payment.objects.filter(activity__site=s, status="paid").aggregate(
                        s=Sum("amount_pennies")
                    )["s"]
                    or 0
                )
                / 100,
            }
        )

    return render(
        request,
        "payments/headoffice/sites.html",
        {"site_data": site_data},
    )


@login_required
@user_passes_test(is_staff)
def site_add(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            from django.utils.text import slugify

            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Site.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            Site.objects.create(name=name, slug=slug)
            messages.success(request, f'Site "{name}" created.')
            return redirect("headoffice_sites")
        else:
            messages.error(request, "Site name is required.")

    return render(request, "payments/headoffice/site_form.html", {"site": None})


@login_required
@user_passes_test(is_staff)
def site_edit(request, site_id):
    site = get_object_or_404(Site, id=site_id)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            site.name = name
            site.is_active = request.POST.get("is_active") == "on"
            site.save()
            messages.success(request, f'Site "{name}" updated.')
            return redirect("headoffice_sites")
        else:
            messages.error(request, "Site name is required.")

    return render(
        request, "payments/headoffice/site_form.html", {"site": site}
    )


@login_required
@user_passes_test(is_staff)
def site_activities_list(request, site_id):
    site = get_object_or_404(Site, id=site_id)
    activities = site.activities.all().order_by("-start_date")

    return render(
        request,
        "payments/headoffice/site_activities.html",
        {"site": site, "activities": activities},
    )


# ── Activities (global) ──────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def activities_list(request):
    activities = Activity.objects.select_related("site").all().order_by("-start_date")

    return render(
        request,
        "payments/headoffice/activities.html",
        {"activities": activities, "company_wide_name": COMPANY_WIDE_NAME},
    )


@login_required
@user_passes_test(is_staff)
def activity_create(request):
    if request.method == "POST":
        form = HeadofficeActivityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Activity created successfully.")
            return redirect("headoffice_activities")
    else:
        form = HeadofficeActivityForm()

    return render(
        request,
        "payments/headoffice/activity_form.html",
        {"form": form, "activity": None},
    )


@login_required
@user_passes_test(is_staff)
def activity_edit(request, activity_id):
    activity = get_object_or_404(Activity, id=activity_id)
    if request.method == "POST":
        form = HeadofficeActivityForm(request.POST, instance=activity)
        if form.is_valid():
            form.save()
            messages.success(request, f"Activity '{activity.name}' updated.")
            return redirect("headoffice_activities")
    else:
        form = HeadofficeActivityForm(instance=activity)

    return render(
        request,
        "payments/headoffice/activity_form.html",
        {"form": form, "activity": activity},
    )


@login_required
@user_passes_test(is_staff)
def activity_delete(request, activity_id):
    activity = get_object_or_404(Activity, id=activity_id)
    if activity.payments.exists():
        messages.error(
            request,
            "Cannot delete an activity that has payments. Deactivate it instead.",
        )
    else:
        name = activity.name
        activity.delete()
        messages.success(request, f"Activity '{name}' deleted.")
    return redirect("headoffice_activities")


# ── Site Seniors ─────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def seniors_list(request):
    seniors = SiteSenior.objects.select_related("user", "site").all()

    return render(
        request,
        "payments/headoffice/seniors.html",
        {"seniors": seniors},
    )


@login_required
@user_passes_test(is_staff)
def senior_create(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        password = request.POST.get("password", "")
        site_id = request.POST.get("site_id")

        if not (email and first_name and last_name and password and site_id):
            messages.error(request, "All fields are required.")
        elif User.objects.filter(username__iexact=email).exists():
            messages.error(request, f"A user with email {email} already exists.")
        else:
            site = get_object_or_404(Site, id=site_id)
            user = User.objects.create_user(
                username=email.lower(),
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            SiteSenior.objects.create(user=user, site=site)
            messages.success(
                request,
                f"Account created for {first_name} {last_name} at {site.name}. "
                f"They can log in with: {email}",
            )
            return redirect("headoffice_seniors")

    sites = Site.objects.filter(is_active=True)
    return render(
        request,
        "payments/headoffice/senior_form.html",
        {"sites": sites},
    )


@login_required
@user_passes_test(is_staff)
def senior_delete(request, senior_id):
    senior = get_object_or_404(SiteSenior, id=senior_id)
    name = str(senior)
    senior.user.delete()
    senior.delete()
    messages.success(request, f"Removed {name}.")
    return redirect("headoffice_seniors")


# ── Payments / Finance ───────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def payments_list(request):
    payments = (
        Payment.objects.select_related("activity__site")
        .all()
        .order_by("-created_at")
    )

    topups = (
        WalletTransaction.objects.filter(transaction_type="topup")
        .select_related("wallet__user")
        .order_by("-created_at")
    )

    # Filter by site
    site_id = request.GET.get("site")
    if site_id:
        payments = payments.filter(activity__site_id=site_id)

    # Filter by status
    status = request.GET.get("status")
    if status:
        payments = payments.filter(status=status)

    # Filter by date range (applies to both tables)
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        payments = payments.filter(paid_at__date__gte=date_from)
        topups = topups.filter(created_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(paid_at__date__lte=date_to)
        topups = topups.filter(created_at__date__lte=date_to)

    sites = Site.objects.all()
    now = timezone.now()
    # Derive year from date_from so month links match the filtered year
    from datetime import datetime as dt
    csv_year = now.year
    if date_from:
        try:
            csv_year = dt.strptime(date_from, "%Y-%m-%d").year
        except (ValueError, TypeError):
            pass
    elif date_to:
        try:
            csv_year = dt.strptime(date_to, "%Y-%m-%d").year
        except (ValueError, TypeError):
            pass
    return render(
        request,
        "payments/headoffice/payments.html",
        {
            "payments": payments,
            "topups": topups,
            "sites": sites,
            "current_year": now.year,
            "csv_year": csv_year,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@login_required
@user_passes_test(is_staff)
def csv_export(request):
    year = request.GET.get("year")
    month = request.GET.get("month")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    site_id = request.GET.get("site")
    status = request.GET.get("status")

    payments = Payment.objects.all().select_related("activity__site")
    if status is None:
        payments = payments.filter(status="paid")
    elif status:
        payments = payments.filter(status=status)
    if site_id:
        payments = payments.filter(activity__site_id=site_id)

    if year and month:
        payments = payments.filter(paid_at__year=year, paid_at__month=month)
        filename = f"payments_{year}_{month.zfill(2)}.csv"
    elif date_from or date_to:
        if date_from:
            payments = payments.filter(paid_at__date__gte=date_from)
        if date_to:
            payments = payments.filter(paid_at__date__lte=date_to)
        if date_from and date_to:
            filename = f"payments_{date_from}_to_{date_to}.csv"
        elif date_from:
            filename = f"payments_from_{date_from}.csv"
        else:
            filename = f"payments_until_{date_to}.csv"
    else:
        filename = "payments_all.csv"

    response = HttpResponse(
        content="\ufeff",  # UTF-8 BOM — Excel needs this to detect the encoding
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"

    writer = csv.writer(response, quoting=csv.QUOTE_ALL)
    writer.writerow(
        [
            "Site",
            "Activity",
            "Service User",
            "Normalized Name",
            "Amount (£)",
            "Status",
            "Is Test",
            "Paid At",
            "Payment Method",
        ]
    )
    for p in payments:
        writer.writerow(
            [
                p.activity.display_site_name,
                p.activity.name,
                p.service_user_name,
                p.normalized_name or p.service_user_name,
                f"{p.amount_pounds:.2f}",
                p.status,
                "Yes" if p.is_test else "No",
                p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "",
                p.get_payment_method_display(),
            ]
        )
    return response


@login_required
@user_passes_test(is_staff)
def csv_topups_export(request):
    year = request.GET.get("year")
    month = request.GET.get("month")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    topups = WalletTransaction.objects.filter(transaction_type="topup").select_related("wallet__user")

    if year and month:
        topups = topups.filter(created_at__year=year, created_at__month=month)
        filename = f"topups_{year}_{month.zfill(2)}.csv"
    elif date_from or date_to:
        if date_from:
            topups = topups.filter(created_at__date__gte=date_from)
        if date_to:
            topups = topups.filter(created_at__date__lte=date_to)
        if date_from and date_to:
            filename = f"topups_{date_from}_to_{date_to}.csv"
        elif date_from:
            filename = f"topups_from_{date_from}.csv"
        else:
            filename = f"topups_until_{date_to}.csv"
    else:
        filename = "topups_all.csv"

    response = HttpResponse(
        content="\ufeff",
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"

    writer = csv.writer(response, quoting=csv.QUOTE_ALL)
    writer.writerow(
        [
            "Account Holder",
            "Email",
            "Amount (£)",
            "Description",
            "Created At",
            "Payment Intent ID",
        ]
    )
    for t in topups:
        writer.writerow(
            [
                t.wallet.user.get_full_name() or t.wallet.user.username,
                t.wallet.user.email,
                f"{t.amount_pounds:.2f}",
                t.description,
                t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
                t.stripe_payment_intent_id,
            ]
        )
    return response


@login_required
@user_passes_test(is_staff)
def csv_combined_export(request):
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    site_id = request.GET.get("site")
    status = request.GET.get("status")

    payments = Payment.objects.all().select_related("activity__site")
    if status is None:
        payments = payments.filter(status="paid")
    elif status:
        payments = payments.filter(status=status)
    if site_id:
        payments = payments.filter(activity__site_id=site_id)
    if date_from:
        payments = payments.filter(paid_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(paid_at__date__lte=date_to)

    topups = WalletTransaction.objects.filter(transaction_type="topup").select_related("wallet__user")
    if date_from:
        topups = topups.filter(created_at__date__gte=date_from)
    if date_to:
        topups = topups.filter(created_at__date__lte=date_to)

    if date_from and date_to:
        filename = f"all_transactions_{date_from}_to_{date_to}.csv"
    elif date_from:
        filename = f"all_transactions_from_{date_from}.csv"
    elif date_to:
        filename = f"all_transactions_until_{date_to}.csv"
    else:
        filename = "all_transactions.csv"

    response = HttpResponse(
        content="\ufeff",
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f"attachment; filename={filename}"

    writer = csv.writer(response, quoting=csv.QUOTE_ALL)
    writer.writerow([
        "Type", "Site", "Account / Service User", "Activity",
        "Amount (£)", "Status", "Date", "Payment Method", "Payment Intent ID",
    ])

    for p in payments:
        writer.writerow([
            "Activity Payment",
            p.activity.display_site_name,
            p.normalized_name or p.service_user_name,
            p.activity.name,
            f"{p.amount_pounds:.2f}",
            p.status,
            p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "",
            p.get_payment_method_display(),
            p.stripe_payment_intent_id,
        ])

    for t in topups:
        writer.writerow([
            "Top-Up",
            "",
            t.wallet.user.get_full_name() or t.wallet.user.username,
            "",
            f"{t.amount_pounds:.2f}",
            "completed",
            t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
            "Card",
            t.stripe_payment_intent_id,
        ])

    return response


# ── Account Holders (Parent/Carer/Service User Accounts) ─────────────────


@login_required
@user_passes_test(is_staff)
def account_holders_list(request):
    users_with_wallets = User.objects.filter(
        wallet__isnull=False, is_staff=False
    ).exclude(site_senior__isnull=False).order_by("last_name", "first_name")

    holders = []
    for u in users_with_wallets:
        service_users = list(u.service_users.all())
        holders.append({
            "user": u,
            "wallet": u.wallet,
            "service_users": service_users,
            "payment_count": Payment.objects.filter(paid_by=u).count(),
        })

    return render(
        request,
        "payments/headoffice/account_holders.html",
        {"holders": holders},
    )


@login_required
@user_passes_test(is_staff)
def account_holder_create(request):
    if request.method == "POST":
        form = AccountHolderUserForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            password = form.cleaned_data["password"]
            site = form.cleaned_data.get("site")
            su_names = form.cleaned_data.get("service_user_names", "")

            user = User.objects.create_user(
                username=email.lower(),
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            Wallet.objects.create(user=user)

            if su_names:
                for line in su_names.split("\n"):
                    line = line.strip()
                    if line:
                        ServiceUser.objects.create(
                            account=user,
                            name=line,
                            site=site,
                        )

            messages.success(
                request,
                f"Account created for {first_name} {last_name}. "
                f"They can log in with: {email}",
            )
            return redirect("headoffice_account_holders")
    else:
        form = AccountHolderUserForm()

    return render(
        request,
        "payments/headoffice/account_holder_form.html",
        {"form": form, "editing": False},
    )


@login_required
@user_passes_test(is_staff)
def account_holder_detail(request, user_id):
    user = get_object_or_404(
        User.objects.filter(wallet__isnull=False, is_staff=False),
        id=user_id,
    )
    wallet = user.wallet
    service_users = user.service_users.all()
    transactions = wallet.transactions.all()[:30]
    payments = Payment.objects.filter(paid_by=user).select_related("activity__site").order_by("-created_at")[:30]

    return render(
        request,
        "payments/headoffice/account_holder_detail.html",
        {
            "holder_user": user,
            "wallet": wallet,
            "service_users": service_users,
            "transactions": transactions,
            "payments": payments,
        },
    )


@login_required
@user_passes_test(is_staff)
def account_holder_edit(request, user_id):
    user = get_object_or_404(
        User.objects.filter(wallet__isnull=False, is_staff=False),
        id=user_id,
    )

    if request.method == "POST":
        form = AccountHolderEditForm(request.POST, instance=user)
        if form.is_valid():
            user.email = form.cleaned_data["email"]
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.is_active = form.cleaned_data["is_active"]
            user.save()

            # Update username to match email
            if user.username != user.email.lower():
                user.username = user.email.lower()
                user.save(update_fields=["username"])

            # Update service users
            existing_sus = list(user.service_users.all())
            new_names = [n.strip() for n in form.cleaned_data.get("service_user_names", "").split("\n") if n.strip()]
            existing_names = {su.name for su in existing_sus}

            # Delete removed
            for su in existing_sus:
                if su.name not in new_names:
                    su.delete()

            # Create new
            for name in new_names:
                if name not in existing_names:
                    ServiceUser.objects.create(account=user, name=name, site=form.cleaned_data.get("site"))

            messages.success(request, f"Account updated for {user.get_full_name()}.")
            return redirect("headoffice_account_holder_detail", user_id=user.id)
    else:
        su_names = "\n".join(su.name for su in user.service_users.all())
        form = AccountHolderEditForm(initial={
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "site": None,
            "service_user_names": su_names,
        }, instance=user)

    return render(
        request,
        "payments/headoffice/account_holder_form.html",
        {"form": form, "editing": True, "holder_user": user},
    )


@login_required
@user_passes_test(is_staff)
def account_holder_delete(request, user_id):
    user = get_object_or_404(
        User.objects.filter(wallet__isnull=False, is_staff=False),
        id=user_id,
    )
    name = user.get_full_name() or user.username
    user.delete()
    messages.success(request, f"Removed account for {name}.")
    return redirect("headoffice_account_holders")


# ── Settings ──────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def settings_view(request):
    su_setting, _ = AppSetting.objects.get_or_create(
        key="su_accounts_enabled",
        defaults={"value": "True"},
    )
    wallet_setting, _ = AppSetting.objects.get_or_create(
        key="wallet_system_enabled",
        defaults={"value": "False"},
    )
    deposit_setting, _ = AppSetting.objects.get_or_create(
        key="max_deposit_amount",
        defaults={"value": "100"},
    )

    if request.method == "POST":
        su_setting.value = "True" if request.POST.get("su_accounts_enabled") == "on" else "False"
        su_setting.save()

        wallet_on = request.POST.get("wallet_system_enabled") == "on"
        # Wallet requires SU accounts to be active
        if wallet_on and su_setting.bool_value is False:
            wallet_on = False
        wallet_setting.value = "True" if wallet_on else "False"
        wallet_setting.save()

        max_dep = request.POST.get("max_deposit_amount", "100").strip()
        try:
            dep_val = int(max_dep)
            if dep_val < 1:
                dep_val = 100
            deposit_setting.value = str(dep_val)
        except ValueError:
            deposit_setting.value = "100"
        deposit_setting.save()

        messages.success(request, "Settings saved.")
        return redirect("headoffice_settings")

    return render(
        request,
        "payments/headoffice/settings.html",
        {
            "su_accounts_enabled": su_setting.bool_value,
            "wallet_system_enabled": wallet_setting.bool_value,
            "max_deposit_amount": deposit_setting.int_value,
        },
    )
