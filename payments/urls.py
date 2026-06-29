from django.urls import path
from . import views
from . import views_headoffice
from . import views_accounts

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
    # ── Account holder panel ─────────────────────────────────────────────
    path("account/dashboard/", views_accounts.account_dashboard, name="account_dashboard"),
    path("account/balance/", views_accounts.account_balance, name="account_balance"),
    path("account/top-up/", views_accounts.account_topup, name="account_topup"),
    path("account/top-up/success/", views_accounts.account_topup_success, name="account_topup_success"),
    path("account/top-up/cancelled/", views_accounts.account_topup_cancelled, name="account_topup_cancelled"),
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
    path("headoffice/payments/export-topups-csv/", views_headoffice.csv_topups_export, name="headoffice_csv_topups_export"),
    path("headoffice/payments/export-combined-csv/", views_headoffice.csv_combined_export, name="headoffice_csv_combined_export"),
    path("headoffice/account-holders/", views_headoffice.account_holders_list, name="headoffice_account_holders"),
    path("headoffice/account-holders/new/", views_headoffice.account_holder_create, name="headoffice_account_holder_create"),
    path("headoffice/account-holders/<int:user_id>/", views_headoffice.account_holder_detail, name="headoffice_account_holder_detail"),
    path("headoffice/account-holders/<int:user_id>/edit/", views_headoffice.account_holder_edit, name="headoffice_account_holder_edit"),
    path("headoffice/account-holders/<int:user_id>/delete/", views_headoffice.account_holder_delete, name="headoffice_account_holder_delete"),
    path("headoffice/settings/", views_headoffice.settings_view, name="headoffice_settings"),
]
