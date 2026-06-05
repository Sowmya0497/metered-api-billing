from django.urls import path
from .views import PaymentWebhookView

urlpatterns = [
    path('payments/', PaymentWebhookView.as_view()),
]
