from django.urls import path

from . import views

urlpatterns = [
    # Dashboard
    path('secretary/', views.secretary_dashboard, name='secretary_dashboard'),

    # ----- Visitor coordination -----
    path('secretary/visitors/',                      views.visitor_feed,               name='secretary_visitor_feed'),
    path('secretary/visitors/<int:pk>/',             views.visitor_detail,             name='secretary_visitor_detail'),
    path('secretary/visitors/<int:visitor_id>/issue-pass/', views.official_pass_issue,  name='secretary_official_pass_issue'),
    path('secretary/visitors/<int:visitor_id>/confirm-signature/', views.confirm_admin_signature, name='secretary_confirm_signature'),
    path('secretary/visitors/<int:visitor_id>/checkout/', views.checkout_official_visitor, name='secretary_checkout_visitor'),

    # ----- Appointments -----
    path('secretary/appointments/',                     views.appointment_list,     name='secretary_appointment_list'),
    path('secretary/appointments/create/',              views.appointment_create,   name='secretary_appointment_create'),
    path('secretary/appointments/<int:pk>/',            views.appointment_detail,   name='secretary_appointment_detail'),
    path('secretary/appointments/<int:pk>/confirm/',    views.appointment_confirm,  name='secretary_appointment_confirm'),
    path('secretary/appointments/<int:pk>/complete/',   views.appointment_complete, name='secretary_appointment_complete'),
    path('secretary/appointments/<int:pk>/cancel/',     views.appointment_cancel,   name='secretary_appointment_cancel'),

    # ----- Correspondence -----
    path('secretary/correspondence/',              views.correspondence_list,   name='secretary_correspondence_list'),
    path('secretary/correspondence/create/',       views.correspondence_create, name='secretary_correspondence_create'),
    path('secretary/correspondence/<int:pk>/',     views.correspondence_detail, name='secretary_correspondence_detail'),
    path('secretary/correspondence/<int:pk>/edit/',views.correspondence_edit,   name='secretary_correspondence_edit'),

    # ----- Notices -----
    path('secretary/notices/',           views.notice_list,   name='secretary_notice_list'),
    path('secretary/notices/create/',    views.notice_create, name='secretary_notice_create'),
    path('secretary/notices/<int:pk>/edit/', views.notice_edit, name='secretary_notice_edit'),
    
        # ----- Notice Printing -----
    path('secretary/notices/<int:pk>/print/',
         views.notice_print, name='secretary_notice_print'),
    path('secretary/notices/print-all/',
         views.notice_print_all, name='secretary_notice_print_all'),

    # ----- Admission Applications -----
    path('secretary/admissions/',                 views.application_list,   name='secretary_application_list'),
    path('secretary/admissions/create/',          views.application_create, name='secretary_application_create'),
    path('secretary/admissions/<int:pk>/',        views.application_detail, name='secretary_application_detail'),
    path('secretary/admissions/<int:pk>/edit/',   views.application_edit,   name='secretary_application_edit'),
        # ----- Letter Templates -----
    path('secretary/letter-templates/',           views.letter_template_list, name='secretary_letter_template_list'),
    path('secretary/letter-templates/<int:pk>/edit/', views.letter_template_edit, name='secretary_letter_template_edit'),

    # ----- Generated Letters -----
    path('secretary/letters/',                    views.letter_list,             name='secretary_letter_list'),
    path('secretary/letters/create/',             views.letter_create,           name='secretary_letter_create'),
    path('secretary/letters/<int:pk>/',           views.letter_detail,           name='secretary_letter_detail'),
    path('secretary/letters/<int:pk>/print/',     views.letter_print,            name='secretary_letter_print'),
    path('secretary/letters/<int:pk>/collect/',   views.letter_mark_collected,   name='secretary_letter_mark_collected')
]