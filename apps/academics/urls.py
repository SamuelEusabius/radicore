from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ClassLevelViewSet, SubjectViewSet, TimetableViewSet,
    timetable_grid, timetable_manage, timetable_add, timetable_edit, timetable_delete,
)

router = DefaultRouter()
router.register('classes', ClassLevelViewSet, basename='class-level')
router.register('subjects', SubjectViewSet, basename='subject')
router.register('timetables', TimetableViewSet, basename='timetable')

urlpatterns = router.urls + [
    path('grid/', timetable_grid, name='timetable_grid'),
    path('manage/', timetable_manage, name='timetable_manage'),
    path('add/', timetable_add, name='timetable_add'),
    path('<int:entry_id>/edit/', timetable_edit, name='timetable_edit'),
    path('<int:entry_id>/delete/', timetable_delete, name='timetable_delete'),
]