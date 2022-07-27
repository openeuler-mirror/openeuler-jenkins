from django.urls import path
from projects_builders.views import HookView


urlpatterns = [
    path('hooks/', HookView.as_view()),
]
