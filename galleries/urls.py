
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EventViewSet, PhotoViewSet
from . import auth_views


router = DefaultRouter()
router.register("events", EventViewSet)
router.register("photos", PhotoViewSet)

urlpatterns = [
    path("auth/csrf/", auth_views.csrf_token, name="csrf-token"),
    path("auth/me/", auth_views.current_user, name="current-user"),
    path("auth/register/", auth_views.register, name="register"),
    path("auth/login/", auth_views.login_user, name="login"),
    path("auth/logout/", auth_views.logout_user, name="logout"),
]

urlpatterns += router.urls
