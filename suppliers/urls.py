from os import path

from suppliers.views import SupplierDetailView, SupplierListCreateView


urlpatterns = [
    path("", SupplierListCreateView.as_view(), name="supplier-list"),
    path("<int:pk>/", SupplierDetailView.as_view(), name="supplier-detail"),
]