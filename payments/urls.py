from django.urls import path
from . import views
from . import views_headoffice

urlpatterns = [
    # ── Public payment flow ──────────────────────────────────────────────
    path("", views.home, name="home"),
    path("silva-care-wide/", views.company_wide_activities, name="company_wide_activities"),
    path("sites/<slug:site_slug>/", views.site_activities, name="site_activities"),
    path("activities/<int:activity_id>/pay/", views.activity_pay, name="activity_pay"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/cancelled/", views.payment_cancelled, name="payment_cancelled"),
    path("payment/webhook/", views.stripe_webhook, name="stripe_webhook"),
    # ── Site senior panel ────────────────────────────────────────────────
    path("site/dashboard/", views.site_dashboard, name="site_dashboard"),
    path("site/activities/", views.site_manage_activities, name="site_manage_activities"),
    path("site/activities/new/", views.site_activity_edit, name="site_activity_new"),
    path("site/activities/<int:activity_id>/edit/", views.site_activity_edit, name="site_activity_edit"),
    path("site/activities/<int:activity_id>/delete/", views.site_activity_delete, name="site_activity_delete"),
    path("site/payments/", views.site_payments_view, name="site_payments"),
    # ── Headoffice panel ─────────────────────────────────────────────────
    path("headoffice/", views_headoffice.dashboard, name="headoffice_dashboard"),
    path("headoffice/sites/", views_headoffice.sites_list, name="headoffice_sites"),
    path("headoffice/sites/add/", views_headoffice.site_add, name="headoffice_site_add"),
    path("headoffice/sites/<int:site_id>/edit/", views_headoffice.site_edit, name="headoffice_site_edit"),
    path("headoffice/sites/<int:site_id>/activities/", views_headoffice.site_activities_list, name="headoffice_site_activities"),
    path("headoffice/activities/", views_headoffice.activities_list, name="headoffice_activities"),
    path("headoffice/activities/new/", views_headoffice.activity_create, name="headoffice_activity_create"),
    path("headoffice/activities/<int:activity_id>/edit/", views_headoffice.activity_edit, name="headoffice_activity_edit"),
    path("headoffice/activities/<int:activity_id>/delete/", views_headoffice.activity_delete, name="headoffice_activity_delete"),
    path("headoffice/seniors/", views_headoffice.seniors_list, name="headoffice_seniors"),
    path("headoffice/seniors/new/", views_headoffice.senior_create, name="headoffice_senior_create"),
    path("headoffice/seniors/<int:senior_id>/delete/", views_headoffice.senior_delete, name="headoffice_senior_delete"),
    path("headoffice/payments/", views_headoffice.payments_list, name="headoffice_payments"),
    path("headoffice/payments/export-csv/", views_headoffice.csv_export, name="headoffice_csv_export"),
]
