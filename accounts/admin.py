from django.contrib import admin

from .models import ActivityLog, User

admin.site.register(User)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user_name", "user_role", "action", "summary")
    list_filter = ("action", "user_role")
    search_fields = ("user_name", "summary", "target_label")
    readonly_fields = [f.name for f in ActivityLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
