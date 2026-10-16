from django.urls import path

from . import views

urlpatterns = [
    # =========================================================
    # Dashboard
    # =========================================================
    path('security/', views.cso_dashboard, name='cso_dashboard'),

    # =========================================================
    # Visitors
    # =========================================================
    path('security/visitors/',                    views.visitor_list,      name='cso_visitor_list'),
    path('security/visitors/check-in/',           views.visitor_check_in,  name='cso_visitor_check_in'),
    path('security/visitors/<int:pk>/',           views.visitor_detail,    name='cso_visitor_detail'),
    path('security/visitors/<int:pk>/check-out/', views.visitor_check_out, name='cso_visitor_check_out'),

    # =========================================================
    # Gate Passes
    # =========================================================
    path('security/passes/',                        views.gate_pass_list,   name='cso_gate_pass_list'),
    path('security/passes/<int:pk>/',               views.gate_pass_detail, name='cso_gate_pass_detail'),
    path('security/passes/issue/<int:visitor_id>/', views.gate_pass_issue,  name='cso_gate_pass_issue'),
    path('security/passes/<int:pk>/print/',         views.gate_pass_print,  name='cso_gate_pass_print'),
    path('security/passes/<int:pk>/cancel/',        views.gate_pass_cancel, name='cso_gate_pass_cancel'),

    # =========================================================
    # Incidents
    # =========================================================
    path('security/incidents/',               views.incident_list,   name='cso_incident_list'),
    path('security/incidents/create/',        views.incident_create, name='cso_incident_create'),
    path('security/incidents/<int:pk>/',      views.incident_detail, name='cso_incident_detail'),
    path('security/incidents/<int:pk>/edit/', views.incident_edit,   name='cso_incident_edit'),

    # =========================================================
    # Lost & Found
    # =========================================================
    path('security/lost-found/',               views.lost_item_list,   name='cso_lost_item_list'),
    path('security/lost-found/create/',        views.lost_item_create, name='cso_lost_item_create'),
    path('security/lost-found/<int:pk>/claim/', views.lost_item_claim, name='cso_lost_item_claim'),

    # =========================================================
    # Shifts
    # =========================================================
    path('security/shifts/',        views.shift_list,   name='cso_shift_list'),
    path('security/shifts/create/', views.shift_create, name='cso_shift_create'),
]