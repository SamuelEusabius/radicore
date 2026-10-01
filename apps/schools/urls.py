from rest_framework.routers import DefaultRouter
from .views import SchoolViewSet, SubscriptionPlanViewSet

router = DefaultRouter()
router.register('list', SchoolViewSet, basename='school')
router.register('plans', SubscriptionPlanViewSet, basename='plan')
urlpatterns = router.urls