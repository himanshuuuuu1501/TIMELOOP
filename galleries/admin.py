
from django.contrib import admin
from .models import Event, Photo


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "event_date", "created_at")
    search_fields = ("name",)
    list_filter = ("event_date",)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "event", "uploaded_at")
    search_fields = ("original_filename", "event__name")
    list_filter = ("event", "uploaded_at")
