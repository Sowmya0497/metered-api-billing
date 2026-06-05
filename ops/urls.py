from django.urls import path
from .views import (
    CustomerListView, CustomerDetailView,
    IssueCreditView, LineItemOverrideView,
    AnomalyListView, CreditListView, CreditDetailView,
)

urlpatterns = [
    path('customers/', CustomerListView.as_view()),
    path('customers/<uuid:customer_id>/', CustomerDetailView.as_view()),
    path('customers/<uuid:customer_id>/credits/', IssueCreditView.as_view()),
    path('invoices/<uuid:invoice_id>/line-items/<uuid:line_item_id>/', LineItemOverrideView.as_view()),
    path('anomalies/', AnomalyListView.as_view()),
    path('credits/', CreditListView.as_view()),
    path('credits/<uuid:credit_id>/', CreditDetailView.as_view()),
]