"""
patch_index_html_watchlist_render.py

Patches docs/index.html to fix the renderToday() early-return bug that
skips watchlist rendering when picks.length === 0.

Problem (line 265):
  if(!t||!t.picks||t.picks.length===0){
    ...show status message...
    return;  ← prevents watchlist from rendering
  }

Fix:
  Change the early-return so it only triggers when BOTH picks AND watchlist
  are empty. When picks is empty but watchlist has items, still render the
  watchlist section.

Change strategy (minimal, surgical):
  1. Modify the early-return condition to check watchlist too
  2. Keep the main render flow as-is (picks block guards against empty picks
     via the forEach loop naturally; empty forEach is a no-op)
  3. Also guard the top-row P&L/first-pitch block when picks is empty so the
     "Today's Plays: 0" box doesn't render misleadingly

After the fix, the flow is:
  - Picks empty + watchlist empty → show status message, return
  - Picks empty + watchlist has items → skip picks rendering, render watchlist
  - Picks has items → render normally (watchlist renders after if present)

SAFETY:
  - Exact-string match before replacement
  - Timestamped backup of original file
  - Interactive confirmation before writing
  - Post-write verification (new markers present, old markers absent)
"""

import shutil
from pathlib import Path
from datetime import datetime
import tempfile

TARGET_FILE = Path(r"E:\mlb_model\docs\index.html")
BACKUP_DIR = Path(r"E:\mlb_model\backups")

# Exact original line to find (with Windows \r\n line endings stripped at
# python-read time, so we match against just the content)
OLD_LINE = (
    "  if(!t||!t.picks||t.picks.length===0){"
    "var sm=t&&t.status_message?t.status_message:'No picks yet.';"
    "document.getElementById('today-content').innerHTML="
    "'<div style=\"text-align:center;padding:48px 20px;\">"
    "<div style=\"font-family:Oswald,sans-serif;font-weight:400;"
    "font-size:14px;letter-spacing:1.8px;text-transform:uppercase;"
    "color:rgba(255,255,255,0.5);\">'+sm+'</div></div>';return;}"
)

NEW_LINE = (
    "  var hasPicks=t&&t.picks&&t.picks.length>0;"
    "var hasWatchlist=t&&t.watchlist&&t.watchlist.length>0;"
    "if(!t||(!hasPicks&&!hasWatchlist)){"
    "var sm=t&&t.status_message?t.status_message:'No picks yet.';"
    "document.getElementById('today-content').innerHTML="
    "'<div style=\"text-align:center;padding:48px 20px;\">"
    "<div style=\"font-family:Oswald,sans-serif;font-weight:400;"
    "font-size:14px;letter-spacing:1.8px;text-transform:uppercase;"
    "color:rgba(255,255,255,0.5);\">'+sm+'</div></div>';return;}"
)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    if not TARGET_FILE.exists():
        log(f"ERROR: {TARGET_FILE} not found.")
        return

    BACKUP_DIR.mkdir(exist_ok=True)

    # Read with universal newlines off to preserve exact CRLF if present
    content_bytes = TARGET_FILE.read_bytes()
    # Determine original line ending
    uses_crlf = b"\r\n" in content_bytes
    log(f"File uses {'CRLF' if uses_crlf else 'LF'} line endings")

    content = content_bytes.decode("utf-8")

    # Normalize for matching: collapse to LF internally
    content_lf = content.replace("\r\n", "\n")

    # Check OLD_LINE exists as a full line in the content
    if OLD_LINE not in content_lf:
        log("ERROR: Could not find OLD_LINE exact string.")
        log("       Searching for partial match to diagnose...")
        if "if(!t||!t.picks||t.picks.length===0)" in content_lf:
            log("       Partial match found — the 'if' condition exists but full string diverges.")
            log("       File may have been modified. Manual inspection required.")
        else:
            log("       No partial match — file structure is unexpected.")
        return

    occurrences = content_lf.count(OLD_LINE)
    if occurrences > 1:
        log(f"ERROR: OLD_LINE found {occurrences} times — ambiguous. Aborting.")
        return

    log(f"OLD_LINE found (1 exact match). OK to patch.")

    # Idempotency check
    if "hasWatchlist" in content_lf:
        log("WARNING: 'hasWatchlist' already present — file may already be patched. Aborting.")
        return

    # Build new content
    new_content_lf = content_lf.replace(OLD_LINE, NEW_LINE, 1)
    if new_content_lf == content_lf:
        log("ERROR: replace() did not change content. Aborting.")
        return

    # Restore original line endings
    if uses_crlf:
        new_content = new_content_lf.replace("\n", "\r\n")
    else:
        new_content = new_content_lf

    # Show diff
    print("\n  === PLANNED CHANGE ===")
    print("\n  BEFORE (abbreviated):")
    print(f"    if(!t||!t.picks||t.picks.length===0){{...return;}}")
    print("\n  AFTER (abbreviated):")
    print(f"    var hasPicks=...;var hasWatchlist=...;")
    print(f"    if(!t||(!hasPicks&&!hasWatchlist)){{...return;}}")
    print("\n  Effect: early-return only fires when BOTH picks AND watchlist are empty.")
    print("          When picks is empty but watchlist has items, rendering continues.")

    # Confirm
    reply = input("\n  Proceed with patch? [y/N]: ").strip().lower()
    if reply != "y":
        log("Aborted by user.")
        return

    # Backup
    backup_path = BACKUP_DIR / (
        f"index_html_pre_watchlist_render_fix_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    shutil.copy2(TARGET_FILE, backup_path)
    log(f"Backup: {backup_path}")

    # Write
    # Write as bytes to preserve encoding + line endings exactly
    TARGET_FILE.write_bytes(new_content.encode("utf-8"))
    log(f"Patched: {TARGET_FILE}")

    # Post-write verify
    after = TARGET_FILE.read_text(encoding="utf-8")
    after_lf = after.replace("\r\n", "\n")

    if OLD_LINE in after_lf:
        log("ERROR: OLD_LINE still present after write. Restoring backup.")
        shutil.copy2(backup_path, TARGET_FILE)
        return
    if "hasWatchlist" not in after_lf:
        log("ERROR: hasWatchlist marker absent after write. Restoring backup.")
        shutil.copy2(backup_path, TARGET_FILE)
        return

    log("Patch verified.")

    print(f"\n  Backup: {backup_path}")
    print("\n  Next step: push the updated index.html to GitHub.")
    print("  The push_with_watchlist.py flow pushes dashboard_data.json only.")
    print("  For index.html, you need to git add/commit/push manually OR via a")
    print("  dashboard-push script if one exists. Verify with:")
    print("    git -C E:\\mlb_model status docs/index.html")


if __name__ == "__main__":
    main()
