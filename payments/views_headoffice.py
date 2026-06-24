import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum, Count
from payments.models import Site, Activity, Payment, SiteSenior, COMPANY_WIDE_NAME
from payments.forms import HeadofficeActivityForm


def is_staff(user):
    return user.is_staff


# ── Dashboard ────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_staff)
def dashboard(request):
    total_sites = Site.objects.count()
    total_activities = Activity.objects.count()
    total_seniors = SiteSenior.objects.count()
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
            "total_paid_pounds": total_paid / 100,
            "payment_count": payment_count,
            "recent_payments": recent_payments,
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

    # Filter by site
    site_id = request.GET.get("site")
    if site_id:
        payments = payments.filter(activity__site_id=site_id)

    # Filter by status
    status = request.GET.get("status")
    if status:
        payments = payments.filter(status=status)

    # Filter by date range
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        payments = payments.filter(paid_at__date__gte=date_from)
    if date_to:
        payments = payments.filter(paid_at__date__lte=date_to)

    sites = Site.objects.all()
    now = timezone.now()
    return render(
        request,
        "payments/headoffice/payments.html",
        {
            "payments": payments,
            "sites": sites,
            "current_year": now.year,
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

    payments = Payment.objects.filter(status="paid").select_related("activity__site")

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
            ]
        )
    return response
