
from django.urls import path
from .views import PersonSearchView

urlpatterns = [
    path(
        "person-search/",
        PersonSearchView.as_view(),
        name="person-search",
    ),
]
