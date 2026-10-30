from django.urls import path
from .views import (
    PersonSearchView,
    SavedMatchesView,
    SceneSearchView,
    PersonMomentSearchView,
)

urlpatterns = [
    path("person-search/", PersonSearchView.as_view(), name="person-search"),
    path("saved-matches/", SavedMatchesView.as_view(), name="saved-matches"),
    path("scene-search/", SceneSearchView.as_view(), name="scene-search"),
    path("person-moment-search/", PersonMomentSearchView.as_view(), name="person-moment-search"),
]