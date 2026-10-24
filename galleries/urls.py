
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, PhotoViewSet

router = DefaultRouter()
router.register("events", EventViewSet)
router.register("photos", PhotoViewSet)

urlpatterns = router.urls
