from django.urls import path
from . import wallet_views

urlpatterns = [
    # Accountant
    path('', wallet_views.wallet_dashboard, name='wallet_dashboard'),
    path('all/', wallet_views.wallet_list, name='wallet_list'),
    path('<int:wallet_id>/', wallet_views.wallet_detail, name='wallet_detail'),
    path('<int:wallet_id>/topup/', wallet_views.wallet_topup, name='wallet_topup'),
    path('<int:wallet_id>/withdraw/', wallet_views.wallet_withdraw, name='wallet_withdraw'),
    path('tx/<int:tx_id>/mark-collected/', wallet_views.wallet_mark_collected, name='wallet_mark_collected'),

    # Class Teacher
    path('teacher/', wallet_views.teacher_wallets, name='teacher_wallets'),
    path('teacher/pending/', wallet_views.teacher_pending_collections, name='teacher_pending_collections'),

    # Parent
    path('parent/', wallet_views.parent_wallets, name='parent_wallets'),
    path('parent/<int:wallet_id>/', wallet_views.parent_child_wallet, name='parent_child_wallet'),

    # Student
    path('me/', wallet_views.student_wallet, name='student_wallet'),
    path('parent/<int:wallet_id>/topup/', wallet_views.parent_wallet_topup, name='parent_wallet_topup'),
]