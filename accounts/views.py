from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from pharmacy_config.pagination import LargeResultsSetPagination

from .audit import diff, log_activity, snapshot
from .models import ActivityLog
from .serializers import (
    ActivityLogSerializer,
    CustomTokenSerializer,
    RegisterSerializer,
    StaffSerializer,
    UserProfileSerializer,
)

User = get_user_model()

# Roles allowed to look at other people's activity (PRD: the Administrator
# views audit/activity logs, the Store Manager monitors employee activity).
PRIVILEGED_ROLES = ("ADMIN", "STORE_MANAGER")


def can_view_team_activity(user):
    return bool(user.is_superuser or user.role in PRIVILEGED_ROLES)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            log_activity(request.user, ActivityLog.LOGOUT, "Signed out")

            return Response(status=status.HTTP_205_RESET_CONTENT)
        except (TokenError, KeyError):
            return Response(status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET the signed-in user's profile; PATCH name, phone or photo.

    The photo is sent as multipart field `avatar`; send `remove_avatar=true`
    to go back to the initials badge."""

    permission_classes = (IsAuthenticated,)
    serializer_class = UserProfileSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = self.request.user
        fields = ["first_name", "last_name", "phone_number", "avatar"]
        before = snapshot(user, fields)

        remove = str(self.request.data.get("remove_avatar", "")).lower() in (
            "1",
            "true",
            "yes",
        )
        if remove and user.avatar:
            user.avatar.delete(save=False)
            serializer.save(avatar=None)
        else:
            serializer.save()

        user.refresh_from_db()
        changes = diff(before, snapshot(user, fields))
        if changes:
            log_activity(
                user,
                ActivityLog.PROFILE_UPDATED,
                "Updated their profile",
                target=user,
                target_label=user.display_name,
                changes=changes,
            )


class ActivityLogListView(generics.ListAPIView):
    """The activity feed.

    * Everyone sees their own activity (default).
    * Administrators and Store Managers can pass `scope=all` or `user=<id>`
      to see what the whole team (or one person) did.

    Filters: action, date (YYYY-MM-DD), date_from, date_to, search.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = ActivityLogSerializer
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        request = self.request
        params = request.query_params
        qs = ActivityLog.objects.select_related("user")

        scope = params.get("scope", "mine")
        who = params.get("user")

        if who and who != "me" and str(who) != str(request.user.pk):
            if not can_view_team_activity(request.user):
                raise PermissionDenied(
                    "Only administrators and store managers can view other staff activity."
                )
            qs = qs.filter(user_id=who)
        elif scope == "all" and who is None:
            if not can_view_team_activity(request.user):
                raise PermissionDenied(
                    "Only administrators and store managers can view team activity."
                )
        else:
            qs = qs.filter(user=request.user)

        action = params.get("action")
        if action:
            qs = qs.filter(action__in=[a.strip() for a in action.split(",") if a.strip()])

        if params.get("date"):
            qs = qs.filter(created_at__date=params["date"])
        if params.get("date_from"):
            qs = qs.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(created_at__date__lte=params["date_to"])

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(summary__icontains=search)
                | Q(target_label__icontains=search)
                | Q(user_name__icontains=search)
            )

        if params.get("hide_sessions") in ("1", "true"):
            qs = qs.exclude(action__in=[ActivityLog.LOGIN, ActivityLog.LOGOUT])

        return qs


class ActivitySummaryView(APIView):
    """Headline numbers for the profile / "My activity" screen."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        who = request.query_params.get("user")
        user = request.user
        if who and who != "me" and str(who) != str(user.pk):
            if not can_view_team_activity(user):
                raise PermissionDenied("Not allowed.")
            user = generics.get_object_or_404(User, pk=who)

        today = timezone.localdate()
        week_start = today - timedelta(days=6)

        mine = ActivityLog.objects.filter(user=user)
        stock_rows = mine.exclude(action__in=ActivityLog.NOT_UPDATES)

        def totals(qs):
            agg = qs.aggregate(
                updates=Count("id"),
                net=Sum("quantity"),
                received=Sum("quantity", filter=Q(quantity__gt=0)),
                dispensed=Sum("quantity", filter=Q(quantity__lt=0)),
            )
            return {
                "updates": agg["updates"] or 0,
                "net_units": agg["net"] or 0,
                "units_in": agg["received"] or 0,
                "units_out": abs(agg["dispensed"] or 0),
            }

        t_today = totals(stock_rows.filter(created_at__date=today))
        t_week = totals(stock_rows.filter(created_at__date__gte=week_start))
        last = mine.exclude(action__in=[ActivityLog.LOGIN, ActivityLog.LOGOUT]).first()

        return Response(
            {
                "user": user.pk,
                "updates_today": t_today["updates"],
                "net_units_today": t_today["net_units"],
                "units_in_today": t_today["units_in"],
                "units_out_today": t_today["units_out"],
                "updates_7d": t_week["updates"],
                "net_units_7d": t_week["net_units"],
                "units_in_7d": t_week["units_in"],
                "units_out_7d": t_week["units_out"],
                "last_action_at": last.created_at if last else None,
                "last_action": last.summary if last else None,
            }
        )


class StaffListView(generics.ListAPIView):
    """Active staff list — used by the 'who did it' filter on team activity."""

    permission_classes = (IsAuthenticated,)
    serializer_class = StaffSerializer
    pagination_class = None

    def get_queryset(self):
        if not can_view_team_activity(self.request.user):
            raise PermissionDenied("Not allowed.")
        return User.objects.filter(is_active=True).order_by("first_name", "username")


class ForgotPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)

            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = PasswordResetTokenGenerator().make_token(user)

            # Normally send an email here
            reset_link = f"https://yourfrontend.com/reset-password/{uidb64}/{token}/"

            return Response(
                {
                    "message": "Password reset link generated.",
                    "reset_link": reset_link,  # Remove this in production
                }
            )

        except User.DoesNotExist:
            return Response(
                {"error": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )


class ResetPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        uidb64 = request.data.get("uidb64")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not uidb64 or not token or not new_password:
            return Response(
                {"error": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

        except Exception:
            return Response(
                {"error": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not PasswordResetTokenGenerator().check_token(user, token):
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password reset successful."}, status=status.HTTP_200_OK
        )
