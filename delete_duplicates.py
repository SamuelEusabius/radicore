"""
Safely remove 3 duplicate function definitions from apps/dashboard/views.py.

Deletes in REVERSE order (highest line numbers first) so remaining line
numbers stay valid.

Before running: back up the file.
"""

import shutil
from pathlib import Path

# --- Configuration ---
VIEWS_FILE = Path("apps/dashboard/views.py")
BACKUP_FILE = Path("apps/dashboard/views.py.before_dup_cleanup")

# Exact line ranges to delete (1-indexed, inclusive)
# Order: highest line numbers first
DELETIONS = [
    # (start_line, end_line, description)
    (7143, 7185, "admin_attendance_export (first copy)"),
    (2336, 2463, "bulk_sms (first copy)"),
    (27, 40, "redirect_dashboard (first copy)"),
]


def main():
    # --- Safety check ---
    if not VIEWS_FILE.exists():
        print(f"ERROR: {VIEWS_FILE} not found. Are you in the project root?")
        return

    # --- Backup ---
    print(f"Backing up to {BACKUP_FILE} ...")
    shutil.copy2(VIEWS_FILE, BACKUP_FILE)
    print("  Backup created.")

    # --- Read file ---
    with open(VIEWS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    original_count = len(lines)
    print(f"  Original line count: {original_count}")

    # --- Delete ranges (in reverse order) ---
    for start, end, desc in DELETIONS:
        # Convert 1-indexed to 0-indexed, inclusive end
        start_idx = start - 1
        end_idx = end  # exclusive (Python slice)
        removed = end_idx - start_idx
        print(f"Deleting lines {start}-{end} ({removed} lines): {desc}")
        del lines[start_idx:end_idx]

    # --- Write back ---
    with open(VIEWS_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)

    new_count = len(lines)
    print(f"\nNew line count: {new_count}")
    print(f"Lines removed: {original_count - new_count}")
    print("\n✅ Done.")
    print(f"\nIf something went wrong, restore with:")
    print(f"  Copy-Item {BACKUP_FILE} {VIEWS_FILE} -Force")


if __name__ == "__main__":
    main()