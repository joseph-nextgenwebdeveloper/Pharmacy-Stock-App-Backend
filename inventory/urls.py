from rest_framework.routers import DefaultRouter
from .views import BatchViewSet, CategoryViewSet, MedicineViewSet, StockMovementViewSet

router = DefaultRouter()

router.register('categories', CategoryViewSet, basename='category')
router.register('medicines', MedicineViewSet, basename='medicine')
router.register('batches', BatchViewSet, basename='batch')
router.register('stock-movements', StockMovementViewSet, basename='stock-movement')
urlpatterns = router.urls