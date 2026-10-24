from django.urls import path

from . import views

app_name = 'boarding'

urlpatterns = [
    # Dashboard
    path('', views.boarding_index, name='boarding_index'),

    # Dormitories
    path('dormitories/', views.dormitory_manage, name='dormitory_manage'),
    path('dormitories/new/', views.dormitory_create, name='dormitory_create'),
    path('dormitories/<int:pk>/edit/', views.dormitory_edit, name='dormitory_edit'),
    path('dormitories/<int:pk>/delete/', views.dormitory_delete, name='dormitory_delete'),

    # Beds
    path('beds/', views.bed_manage, name='bed_manage'),
    path('beds/new/', views.bed_create, name='bed_create'),
    path('beds/bulk/', views.bed_bulk_create, name='bed_bulk_create'),
    path('beds/<int:pk>/edit/', views.bed_edit, name='bed_edit'),
    path('beds/<int:pk>/delete/', views.bed_delete, name='bed_delete'),

    # Assignments
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/new/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:pk>/transfer/', views.assignment_transfer, name='assignment_transfer'),
    path('assignments/<int:pk>/checkout/', views.assignment_checkout, name='assignment_checkout'),
        # Roster downloads
    path('downloads/boarders.csv', views.boarders_csv, name='boarders_csv'),
    path('downloads/boarders.pdf', views.boarders_pdf, name='boarders_pdf'),
    path('downloads/boarders/house/<int:dormitory_id>.csv',
         views.boarders_by_house_csv, name='boarders_by_house_csv'),
    path('downloads/boarders/house/<int:dormitory_id>.pdf',
         views.boarders_by_house_pdf, name='boarders_by_house_pdf'),
]