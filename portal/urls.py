from django.urls import include, path
from django.contrib.auth import views as auth_views
from payments.views import redirect_after_login

urlpatterns = [
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            redirect_authenticated_user=True,
            extra_context={"next": ""},
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/redirect/", redirect_after_login, name="login_redirect"),
    path(
        "accounts/password/",
        include(
            [
                path(
                    "change/",
                    auth_views.PasswordChangeView.as_view(
                        template_name="registration/password_change_form.html",
                    ),
                    name="password_change",
                ),
                path(
                    "change/done/",
                    auth_views.PasswordChangeDoneView.as_view(
                        template_name="registration/password_change_done.html",
                    ),
                    name="password_change_done",
                ),
                path(
                    "reset/",
                    auth_views.PasswordResetView.as_view(
                        template_name="registration/password_reset_form.html",
                        email_template_name="registration/password_reset_email.txt",
                        subject_template_name="registration/password_reset_subject.txt",
                    ),
                    name="password_reset",
                ),
                path(
                    "reset/done/",
                    auth_views.PasswordResetDoneView.as_view(
                        template_name="registration/password_reset_done.html",
                    ),
                    name="password_reset_done",
                ),
                path(
                    "reset/<uidb64>/<token>/",
                    auth_views.PasswordResetConfirmView.as_view(
                        template_name="registration/password_reset_confirm.html",
                    ),
                    name="password_reset_confirm",
                ),
                path(
                    "reset/complete/",
                    auth_views.PasswordResetCompleteView.as_view(
                        template_name="registration/password_reset_complete.html",
                    ),
                    name="password_reset_complete",
                ),
            ]
        ),
    ),
    path("", include("payments.urls")),
]
