from django.urls import path
from .views import InvoiceListView, InvoiceDetailView, InvoiceCountView

urlpatterns = [
    path('', InvoiceListView.as_view()),
    path('count/', InvoiceCountView.as_view()),
    path('<uuid:invoice_id>/', InvoiceDetailView.as_view()),
]