from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
    path('v1/events/', include('usage.urls')),
    path('v1/', include('usage.urls')),        # for GET /v1/usage/
    path('v1/invoices/', include('invoices.urls')),
    path('ops/', include('ops.urls')),
    path('ops/customers/', include('customers.urls')),
    path('webhooks/', include('webhooks.urls')),
]
