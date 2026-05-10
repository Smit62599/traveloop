from django.contrib import admin
from .models import Trip, Stop, Activity, ChecklistItem, Note


# ── Inlines ───────────────────────────────────────────────────────────────────

class StopInline(admin.TabularInline):
    model = Stop
    extra = 1
    fields = ('city_name', 'country', 'start_date', 'end_date', 'order')


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 1
    fields = ('name', 'category', 'cost', 'duration')


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1
    fields = ('name', 'category', 'is_completed')


class NoteInline(admin.TabularInline):
    model = Note
    extra = 1
    fields = ('title', 'content')


# ── Model Admins ──────────────────────────────────────────────────────────────

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'start_date', 'end_date', 'stop_count', 'total_budget')
    list_filter = ('status', 'start_date')
    search_fields = ('name', 'user__username', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [StopInline, ChecklistItemInline, NoteInline]

    def stop_count(self, obj):
        return obj.stops.count()
    stop_count.short_description = 'Stops'

    def total_budget(self, obj):
        return f"${obj.total_budget:.2f}"
    total_budget.short_description = 'Budget'


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ('city_name', 'country', 'trip', 'start_date', 'end_date', 'order', 'stop_budget')
    list_filter = ('country',)
    search_fields = ('city_name', 'trip__name')
    ordering = ('trip', 'order')
    inlines = [ActivityInline]

    def stop_budget(self, obj):
        return f"${obj.stop_budget:.2f}"
    stop_budget.short_description = 'Budget'


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'stop', 'cost', 'duration_display', 'created_at')
    list_filter = ('category',)
    search_fields = ('name', 'stop__city_name', 'stop__trip__name')

    def duration_display(self, obj):
        return obj.duration_display
    duration_display.short_description = 'Duration'


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'trip', 'is_completed', 'created_at')
    list_filter = ('category', 'is_completed')
    search_fields = ('name', 'trip__name')
    list_editable = ('is_completed',)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'trip', 'created_at', 'updated_at')
    search_fields = ('title', 'content', 'trip__name')
    readonly_fields = ('created_at', 'updated_at')
