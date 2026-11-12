from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.models import UserSession, User


@login_required
def security_dashboard(request):
    """Super Admin sees all sessions; ICT Officer sees only their school."""
    if request.user.role not in ('super_admin', 'ict_officer'):
        return redirect('dashboard_home')

    if request.user.role == 'super_admin':
        sessions = UserSession.objects.all().select_related('user', 'school')
        scope = "ALL SCHOOLS (Global)"
    else:
        if request.user.school:
            sessions = UserSession.objects.filter(school=request.user.school).select_related('user', 'school')
            scope = request.user.school.name
        else:
            sessions = UserSession.objects.none()
            scope = "NO SCHOOL ASSIGNED"

    active_sessions = sessions.filter(is_active=True).order_by('-last_activity')
    blocked_sessions = sessions.filter(is_active=False).order_by('-last_activity')[:20]

    return render(request, 'dashboard/security_dashboard.html', {
        'active_sessions': active_sessions,
        'blocked_sessions': blocked_sessions,
        'scope': scope,
    })


@login_required
def force_logout_session(request, session_id):
    """Allows admins to instantly kill a specific session."""
    if request.user.role not in ('super_admin', 'ict_officer'):
        return redirect('dashboard_home')

    if request.method == 'POST':
        session = get_object_or_404(UserSession, id=session_id)
        
        # 1. Prevent the admin from killing their own current session to avoid CSRF errors
        if session.user == request.user:
            messages.error(request, "You cannot kill your own current session. Please log out normally.")
            return redirect('security_dashboard')

        # 2. ICT officer can only kill sessions belonging to their school
        if request.user.role == 'ict_officer':
            if session.school and session.school != request.user.school:
                messages.error(request, "You don't have permission to kill this session.")
                return redirect('security_dashboard')

        if session.is_active:
            session.is_active = False
            session.save()
            messages.success(request, f"Session for {session.user.email} has been terminated.")
        else:
            messages.info(request, "Session was already inactive.")

    return redirect('security_dashboard')


@login_required
def force_logout_user_all(request, user_id):
    """Kills ALL active sessions for a specific user (e.g. compromised account)."""
    if request.user.role not in ('super_admin', 'ict_officer'):
        return redirect('dashboard_home')

    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        
        if request.user.role == 'ict_officer':
            if target_user.school and target_user.school != request.user.school:
                messages.error(request, "You don't have permission to target this user.")
                return redirect('security_dashboard')

        count = UserSession.objects.filter(user=target_user, is_active=True).update(is_active=False)
        messages.success(request, f"Forcefully terminated {count} active sessions for {target_user.email}.")

    return redirect('security_dashboard')