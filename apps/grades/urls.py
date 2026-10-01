from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ExamViewSet, GradeViewSet, report_card_pdf

router = DefaultRouter()
router.register('exams', ExamViewSet, basename='exam')
router.register('', GradeViewSet, basename='grade')

urlpatterns = router.urls + [
    path('report-card/<int:student_id>/<int:exam_id>/pdf/', report_card_pdf, name='report_card_pdf'),
]