from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from django.contrib.auth import logout as auth_logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.shortcuts import render, redirect

from .serializers import RegisterSerializer, UserSerializer
from .permissions import IsSchoolAdmin

User = get_user_model()


# ==========================================================
# DRF API VIEWS
# ==========================================================

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        qs = User.objects.all()
        if not self.request.user.is_super_admin:
            qs = qs.filter(school=self.request.user.school)
        return qs


# ==========================================================
# CUSTOM AUTH PAGES
# ==========================================================

def logout_view(request):
    """Log out the user via GET or POST, then show the branded logout page."""
    if request.user.is_authenticated:
        auth_logout(request)
    return render(request, 'account/logout.html')


def school_blocked(request):
    """Show a message when the user's school subscription is expired."""
    return render(request, 'account/school_blocked.html')
# ==========================================================
# PASSWORD CHANGE (all users)
# ==========================================================

@login_required
def change_password(request):
    """Allow any logged-in user to change their own password."""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        errors = []

        # Validate current password
        if not request.user.check_password(current_password):
            errors.append('Your current password is incorrect.')

        # Validate new password
        if len(new_password) < 8:
            errors.append('New password must be at least 8 characters.')

        if new_password != confirm_password:
            errors.append('New passwords do not match.')

        if new_password == current_password:
            errors.append('New password must be different from current password.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)  # keep user logged in
            messages.success(request, '✅ Your password has been updated successfully.')
            return redirect('change_password')

    return render(request, 'account/change_password.html')


@login_required
def profile_view(request):
    """Simple profile page for all users."""
    return render(request, 'account/profile.html')
# ==========================================================
# SUPER ADMIN PROFILE
# ==========================================================

@login_required
def super_admin_profile(request):
    """Super Admin's own profile — view and edit."""
    if request.user.role != 'super_admin':
        return redirect('profile_view')

    from apps.schools.models import School
    from apps.accounts.models import User
    from apps.finance.models import Payment
    from apps.students.models import Student

    user = request.user

    if request.method == 'POST':
        # Update profile fields
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.phone = request.POST.get('phone', '').strip()

        email = request.POST.get('email', '').strip()
        if email and email != user.email:
            # Check uniqueness
            if not User.objects.filter(email=email).exclude(id=user.id).exists():
                user.email = email
                user.username = email
            else:
                messages.error(request, f'Email "{email}" is already in use.')

        # Avatar
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('super_admin_profile')

    # Stats
    stats = {
        'total_schools': School.objects.count(),
        'active_schools': School.objects.filter(is_active=True).count(),
        'total_users': User.objects.count(),
        'total_students': Student.objects.filter(is_active=True).count(),
        'total_payments': Payment.objects.count(),
    }

    return render(request, 'account/super_admin_profile.html', {
        'profile_user': user,
        'stats': stats,
    })