from django.urls import path

from .views import GoodsReceivedListCreateView,GoodsReceivedDetailView


urlpatterns = [
    path("goods-received/",GoodsReceivedListCreateView.as_view(),
        name="goods-received-list-create",),
    path("goods-received/<int:pk>/",GoodsReceivedDetailView.as_view(),
        name="goods-received-detail",),
]