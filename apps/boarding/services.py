"""
Boarding services — the invariants for bed/assignment operations.

Keep all state transitions here so views, admin actions, and management
commands share one code path. Do not add side effects to
BoardingAssignment.save().
"""
from django.db import transaction
from django.utils import timezone

from .models import BoardingAssignment, BoardingBed, BoardingDormitory


class BoardingError(Exception):
    """Raised for any domain rule violation the user should see."""


@transaction.atomic
def assign_bed(student, bed, user=None, notes=''):
    """
    Create a new active assignment for `student` at `bed`.

    If the student already has an active assignment, it is transferred
    (marked TRANSFERRED) before the new one is created.
    """
    if student is None or bed is None:
        raise BoardingError("Student and bed are required.")
    if student.school_id != bed.dormitory.school_id:
        raise BoardingError("Student and bed belong to different schools.")
    if bed.is_occupied:
        raise BoardingError(f"Bed {bed.bed_number} is already occupied.")

    existing = (
        BoardingAssignment.objects
        .filter(student=student, status=BoardingAssignment.Status.ACTIVE)
        .select_related('bed', 'dormitory')
        .first()
    )
    if existing:
        # Re-assigning: mark the old one as transferred, free its bed.
        existing.status = BoardingAssignment.Status.TRANSFERRED
        existing.checked_out_at = timezone.now()
        existing.checkout_reason = "Superseded by new assignment"
        existing.save(update_fields=['status', 'checked_out_at', 'checkout_reason'])
        BoardingBed.objects.filter(pk=existing.bed_id).update(is_occupied=False)

    assignment = BoardingAssignment.objects.create(
        student=student,
        dormitory=bed.dormitory,
        bed=bed,
        status=BoardingAssignment.Status.ACTIVE,
        assigned_by=user,
        notes=notes or '',
    )
    # BoardingAssignment.save() syncs is_occupied; but be explicit here so the
    # caller sees the correct state even before re-fetching.
    BoardingBed.objects.filter(pk=bed.pk).update(is_occupied=True)
    return assignment


@transaction.atomic
def transfer_bed(assignment, new_bed, user=None):
    """
    Move an active assignment to `new_bed`, leaving an audit trail.
    """
    if assignment.status != BoardingAssignment.Status.ACTIVE:
        raise BoardingError("Only active assignments can be transferred.")
    if new_bed is None:
        raise BoardingError("Target bed is required.")
    if new_bed.dormitory.school_id != assignment.student.school_id:
        raise BoardingError("Target bed belongs to a different school.")
    if new_bed.is_occupied:
        raise BoardingError(f"Bed {new_bed.bed_number} is already occupied.")

    old_bed = assignment.bed
    assignment.status = BoardingAssignment.Status.TRANSFERRED
    assignment.checked_out_at = timezone.now()
    assignment.checkout_reason = f"Transferred to {new_bed.dormitory.name} · {new_bed.bed_number}"
    assignment.save(update_fields=['status', 'checked_out_at', 'checkout_reason'])
    BoardingBed.objects.filter(pk=old_bed.pk).update(is_occupied=False)

    new_assignment = BoardingAssignment.objects.create(
        student=assignment.student,
        dormitory=new_bed.dormitory,
        bed=new_bed,
        status=BoardingAssignment.Status.ACTIVE,
        assigned_by=user,
        notes=f"Transferred from {old_bed.dormitory.name} · {old_bed.bed_number}",
    )
    BoardingBed.objects.filter(pk=new_bed.pk).update(is_occupied=True)
    return new_assignment


@transaction.atomic
def checkout_bed(assignment, user=None, reason=''):
    """
    Check out an active assignment and free the bed.
    """
    if assignment.status != BoardingAssignment.Status.ACTIVE:
        raise BoardingError("Only active assignments can be checked out.")
    if not reason or not reason.strip():
        raise BoardingError("A checkout reason is required.")

    assignment.status = BoardingAssignment.Status.CHECKED_OUT
    assignment.checked_out_at = timezone.now()
    assignment.checkout_reason = reason.strip()
    assignment.save(update_fields=['status', 'checked_out_at', 'checkout_reason'])
    BoardingBed.objects.filter(pk=assignment.bed_id).update(is_occupied=False)
    return assignment


def bulk_create_beds(dormitory, prefix, start, count, width):
    """
    Create `count` beds with numbers like f"{prefix}{n:0{width}d}".
    Skips numbers that already exist. Returns (created, skipped).
    """
    if dormitory is None:
        raise BoardingError("Dormitory is required.")
    if count < 1 or count > 200:
        raise BoardingError("Count must be between 1 and 200.")

    existing = set(
        BoardingBed.objects
        .filter(dormitory=dormitory)
        .values_list('bed_number', flat=True)
    )
    to_create = []
    for n in range(start, start + count):
        number = f"{prefix}{n:0{width}d}"
        if number in existing:
            continue
        to_create.append(BoardingBed(dormitory=dormitory, bed_number=number))

    BoardingBed.objects.bulk_create(to_create)
    return len(to_create), count - len(to_create)


def dormitory_has_active_assignments(dormitory):
    return BoardingAssignment.objects.filter(
        dormitory=dormitory, status=BoardingAssignment.Status.ACTIVE
    ).exists()