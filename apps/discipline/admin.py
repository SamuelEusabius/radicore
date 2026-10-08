from django.contrib import admin

from .models import (
    DisciplineRecord,
    DisciplineAction,
    StudentLeaveOut,
    DisciplineCommittee,
    CommitteeMember,
    CommitteeMeeting,
    CommitteeDecision,
)


# ==========================================================
# DISCIPLINE RECORD + ACTIONS
# ==========================================================

class DisciplineActionInline(admin.TabularInline):
    model = DisciplineAction
    extra = 1


@admin.register(DisciplineRecord)
class DisciplineRecordAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'school', 'category', 'severity',
        'status', 'incident_date', 'guardian_notified',
    )
    list_filter = ('school', 'category', 'severity', 'status', 'guardian_notified')
    search_fields = ('student__first_name', 'student__last_name', 'description')
    date_hierarchy = 'incident_date'
    inlines = [DisciplineActionInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DisciplineAction)
class DisciplineActionAdmin(admin.ModelAdmin):
    list_display = ('record', 'action_type', 'performed_by', 'performed_at')
    list_filter = ('action_type',)
    search_fields = ('record__student__first_name', 'record__student__last_name')


# ==========================================================
# COMMITTEES
# ==========================================================

class CommitteeMemberInline(admin.TabularInline):
    model = CommitteeMember
    extra = 0
    fields = ('user', 'role', 'joined_on', 'left_on')


@admin.register(DisciplineCommittee)
class DisciplineCommitteeAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'chairperson', 'formed_on', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'purpose')
    inlines = [CommitteeMemberInline]


@admin.register(CommitteeMember)
class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display = ('committee', 'user', 'role', 'joined_on', 'left_on')
    list_filter = ('role',)


class CommitteeDecisionInline(admin.TabularInline):
    model = CommitteeDecision
    extra = 0
    fields = ('discipline_record', 'decision', 'rationale', 'leave_out')


@admin.register(CommitteeMeeting)
class CommitteeMeetingAdmin(admin.ModelAdmin):
    list_display = ('committee', 'meeting_date', 'meeting_time', 'location', 'minutes_recorded_at')
    list_filter = ('committee', 'meeting_date')
    search_fields = ('agenda', 'minutes')
    date_hierarchy = 'meeting_date'
    inlines = [CommitteeDecisionInline]
    filter_horizontal = ('discipline_records',)


@admin.register(CommitteeDecision)
class CommitteeDecisionAdmin(admin.ModelAdmin):
    list_display = ('get_decision_display', 'meeting', 'discipline_record', 'decided_at', 'recorded_by')
    list_filter = ('decision', 'decided_at')
    search_fields = ('rationale',)


# ==========================================================
# LEAVE-OUTS / SUSPENSIONS
# ==========================================================

@admin.register(StudentLeaveOut)
class StudentLeaveOutAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'school', 'leave_out_type', 'start_date', 'end_date',
        'status', 'guardian_notified', 'actual_return_date',
    )
    list_filter = (
        'school', 'leave_out_type', 'status', 'guardian_notified',
        'suspension_reason',
    )
    search_fields = ('student__first_name', 'student__last_name', 'reason_description')
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at', 'requested_at')