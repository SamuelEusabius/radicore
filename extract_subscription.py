"""
Extract all subscription views from views_old.py into views/subscription.py.

Uses AST to find function boundaries — no manual line counting.
"""

import ast
import shutil
from pathlib import Path

# --- Config ---
SOURCE = Path("apps/dashboard/views_old.py")
TARGET = Path("apps/dashboard/views/subscription.py")

# Functions to extract (in file order)
FUNCTIONS = [
    "subscription_view",
    "subscription_edit_admin",
    "subscription_admin_picker",
    "subscription_payment_pending",
    "subscription_payment_status",
    "confirm_subscription_payment",
    "subscription_plans",
    "subscription_confirm",
    "subscription_payment",
]


def main():
    # --- Read source ---
    source_text = SOURCE.read_text(encoding="utf-8")
    source_lines = source_text.splitlines(keepends=True)
    tree = ast.parse(source_text)

    # --- Find target functions ---
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            # Use decorator lines if present, else function line
            start = node.decorator_list[0].lineno - 1 if node.decorator_list else node.lineno - 1
            end = node.end_lineno  # inclusive, 1-indexed
            found[node.name] = (start, end)

    # --- Verify all found ---
    missing = [f for f in FUNCTIONS if f not in found]
    if missing:
        print(f"ERROR: Missing functions: {missing}")
        return

    print(f"Found {len(found)} functions.")
    for name in FUNCTIONS:
        start, end = found[name]
        print(f"  {name}: lines {start+1}-{end} ({end-start} lines)")

    # --- Extract function source ---
    extracted = {}
    for name in FUNCTIONS:
        start, end = found[name]
        block = "".join(source_lines[start:end])
        extracted[name] = block

    # --- Build target file ---
    target_content = '''"""
Subscription views:
- Plan display and selection
- Subscription management (school admin)
- Super admin subscription management
- Payment flow
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta

from apps.schools.models import SubscriptionPlan, SchoolSubscription, School


'''

    for name in FUNCTIONS:
        target_content += extracted[name].rstrip() + "\n\n\n"

    TARGET.write_text(target_content, encoding="utf-8")
    print(f"\nWrote {TARGET}")

    # --- Remove extracted functions from source ---
    # Sort ranges in reverse so deletion doesn't shift earlier ranges
    ranges = sorted(found.values(), reverse=True)
    for start, end in ranges:
        del source_lines[start:end]

    # --- Collapse excess blank lines ---
    cleaned = []
    blank_run = 0
    for line in source_lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 2:
                cleaned.append(line)
        else:
            blank_run = 0
            cleaned.append(line)

    # --- Backup and write ---
    shutil.copy2(SOURCE, SOURCE.with_suffix(".py.before_sub_extract"))
    SOURCE.write_text("".join(cleaned), encoding="utf-8")

    print(f"Removed functions from {SOURCE}")
    print(f"Backup saved to {SOURCE}.before_sub_extract")
    print("\n✅ Done.")


if __name__ == "__main__":
    main()