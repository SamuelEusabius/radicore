from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.views import logout_view, school_blocked
from apps.accounts.views import logout_view, school_blocked, change_password, profile_view
from apps.accounts.views import logout_view, school_blocked, change_password, profile_view, super_admin_profile

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/password/change/', change_password, name='change_password'),
    path('accounts/profile/', profile_view, name='profile_view'),
    path('departments/', include('apps.departments.urls')),

    # Blocked page (no auth required by middleware)
    path('school-blocked/', school_blocked, name='school_blocked'),

    # Custom logout BEFORE allauth
    path('accounts/logout/', logout_view, name='account_logout'),
    path('accounts/', include('allauth.urls')),

    path('api/accounts/', include('apps.accounts.urls')),
    path('api/schools/', include('apps.schools.urls')),
    path('api/students/', include('apps.students.urls')),
    path('api/teachers/', include('apps.teachers.urls')),
    path('api/parents/', include('apps.parents.urls')),
    path('api/academics/', include('apps.academics.urls')),
    path('api/attendance/', include('apps.attendance.urls')),
    path('api/grades/', include('apps.grades.urls')),
    path('api/finance/', include('apps.finance.urls')),
    path('api/notifications/', include('apps.notifications.urls')),

    path('dashboard/', include('apps.dashboard.urls')),
    path('', include('apps.schools.public_urls')),
    path('accounts/super-admin/profile/', super_admin_profile, name='super_admin_profile'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)