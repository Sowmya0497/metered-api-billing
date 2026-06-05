from django.urls import path
from .views import CustomerListView, CustomerDetailView

urlpatterns = [
    path('', CustomerListView.as_view()),
    path('<uuid:customer_id>/', CustomerDetailView.as_view()),
]
