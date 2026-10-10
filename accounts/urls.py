from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    ActivityLogListView,
    ActivitySummaryView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    RegisterView,
    ResetPasswordView,
    StaffListView,
    UserProfileView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("activity/", ActivityLogListView.as_view(), name="activity-list"),
    path("activity/summary/", ActivitySummaryView.as_view(), name="activity-summary"),
    path("staff/", StaffListView.as_view(), name="staff-list"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]
