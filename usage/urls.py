from django.urls import path
from .views import EventIngestionView, UsageListView

urlpatterns = [
    path('', EventIngestionView.as_view()),      # POST /v1/events/
    path('usage/', UsageListView.as_view()),      # GET  /v1/usage/
]