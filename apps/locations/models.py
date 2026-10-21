"""
Kenya administrative locations.

Cascading hierarchy:
    County → Constituency → Ward

Sub-county is a separate administrative layer that doesn't cascade cleanly,
so we store it as free text on Student/AdmissionApplication.
"""
from django.db import models


# ============================================================
# COUNTY
# ============================================================

class County(models.Model):
    code = models.CharField(
        max_length=10, unique=True, db_index=True,
        help_text="IEBC county code, e.g. 047 for Nairobi"
    )
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Counties'

    def __str__(self):
        return self.name


# ============================================================
# CONSTITUENCY
# ============================================================

class Constituency(models.Model):
    code = models.CharField(
        max_length=10, unique=True, db_index=True,
        help_text="IEBC constituency code"
    )
    name = models.CharField(max_length=120)
    county = models.ForeignKey(
        County, on_delete=models.CASCADE,
        related_name='constituencies'
    )

    class Meta:
        ordering = ['county__name', 'name']
        verbose_name_plural = 'Constituencies'
        indexes = [
            models.Index(fields=['county', 'name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.county.name})"


# ============================================================
# WARD
# ============================================================

class Ward(models.Model):
    code = models.CharField(
        max_length=10, unique=True, db_index=True,
        help_text="IEBC ward code"
    )
    name = models.CharField(max_length=120)
    constituency = models.ForeignKey(
        Constituency, on_delete=models.CASCADE,
        related_name='wards'
    )

    class Meta:
        ordering = ['constituency__name', 'name']
        indexes = [
            models.Index(fields=['constituency', 'name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.constituency.name})"