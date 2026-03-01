#!/usr/bin/env python3
"""GridPulse - Scheduled Watch Mode.

Monitors a folder for PBIP ZIP files and auto-analyzes on changes.

Usage:
    python watcher.py watch /path/to/folder [options]

Options:
    --interval N      Check interval in seconds (default: 30)
    --lang LANG       Language for messages (default: en)
    --webhook URL     POST notification URL on changes
    --output-dir DIR  Directory to save JSON reports
    --min-score N     Alert threshold (print warning if score below N)
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


def _file_hash(path: str) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_folder(folder: str) -> dict[str, str]:
    """Scan folder for ZIP files and return {path: hash} map."""
    files = {}
    for item in os.listdir(folder):
        if item.lower().endswith(".zip"):
            full_path = os.path.join(folder, item)
            if os.path.isfile(full_path):
                files[full_path] = _file_hash(full_path)
    return files


def _send_webhook(url: str, data: dict):
    """Send POST request to webhook URL."""
    try:
        import urllib.request
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  [!] Webhook failed: {e}", file=sys.stderr)


def _run_analysis_for_file(zip_path: str, lang: str) -> dict | None:
    """Run analysis on a single ZIP file."""
    try:
        from cli import run_analysis
        return run_analysis(zip_path, lang=lang)
    except Exception as e:
        print(f"  [!] Analysis failed for {os.path.basename(zip_path)}: {e}", file=sys.stderr)
        return None


def watch(folder: str, interval: int = 30, lang: str = "en",
          webhook: str | None = None, output_dir: str | None = None,
          min_score: int | None = None):
    """Watch a folder for changes and auto-analyze."""
    if not os.path.isdir(folder):
        print(f"Error: Folder not found: {folder}", file=sys.stderr)
        sys.exit(2)

    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    print(f"=== GridPulse Watch Mode ===")
    print(f"  Folder: {os.path.abspath(folder)}")
    print(f"  Interval: {interval}s")
    print(f"  Language: {lang}")
    if webhook:
        print(f"  Webhook: {webhook}")
    if output_dir:
        print(f"  Output: {output_dir}")
    if min_score:
        print(f"  Min score: {min_score}")
    print()

    # Initial scan
    known_files = _scan_folder(folder)
    last_results = {}

    print(f"[{_now()}] Found {len(known_files)} ZIP file(s). Watching for changes...")
    print()

    try:
        while True:
            time.sleep(interval)

            current_files = _scan_folder(folder)

            # Detect changes
            for path, current_hash in current_files.items():
                old_hash = known_files.get(path)
                filename = os.path.basename(path)

                if old_hash is None:
                    # New file
                    print(f"[{_now()}] NEW: {filename}")
                    _process_file(path, filename, lang, webhook, output_dir,
                                  min_score, last_results)
                elif current_hash != old_hash:
                    # Modified file
                    print(f"[{_now()}] MODIFIED: {filename}")
                    _process_file(path, filename, lang, webhook, output_dir,
                                  min_score, last_results)

            # Detect removed files
            for path in set(known_files.keys()) - set(current_files.keys()):
                filename = os.path.basename(path)
                print(f"[{_now()}] REMOVED: {filename}")
                last_results.pop(path, None)

            known_files = current_files

    except KeyboardInterrupt:
        print(f"\n[{_now()}] Watch mode stopped.")


def _process_file(path, filename, lang, webhook, output_dir,
                  min_score, last_results):
    """Analyze a file and handle results."""
    result = _run_analysis_for_file(path, lang)

    if not result or "error" in result:
        error = result.get("error", "Unknown error") if result else "Analysis failed"
        print(f"  Error: {error}")
        return

    score = result["score"]["total_score"]
    grade = result["score"]["grade"]
    findings_count = len(result.get("findings", []))

    # Calculate delta from previous
    prev = last_results.get(path)
    delta = round(score - prev["score"], 1) if prev else None
    delta_str = ""
    if delta is not None:
        delta_str = f"  ({'+' if delta > 0 else ''}{delta})"

    print(f"  Score: {score}/100 ({grade}){delta_str}  |  Findings: {findings_count}")

    # Min score warning
    if min_score and score < min_score:
        print(f"  [WARNING] Score {score} is below threshold {min_score}")

    # Save results
    last_results[path] = {"score": score, "grade": grade}

    # Save JSON report
    if output_dir:
        report_name = os.path.splitext(filename)[0]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(output_dir, f"{report_name}_{ts}.json")
        try:
            from cli import format_json
            json_output = format_json(result)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"  Report saved: {out_path}")
        except Exception as e:
            print(f"  [!] Save failed: {e}", file=sys.stderr)

    # Webhook notification
    if webhook:
        payload = {
            "project_name": result.get("project_name", filename),
            "score": score,
            "grade": grade,
            "delta": delta,
            "findings_count": findings_count,
            "timestamp": datetime.now().isoformat(),
            "file": filename,
        }
        _send_webhook(webhook, payload)

    print()


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(
        description="GridPulse - Watch Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    watch_parser = subparsers.add_parser("watch", help="Watch folder for changes")
    watch_parser.add_argument("folder", help="Folder to watch")
    watch_parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds")
    watch_parser.add_argument("--lang", choices=["en", "es", "pt"], default="en", help="Language")
    watch_parser.add_argument("--webhook", help="Webhook URL for notifications")
    watch_parser.add_argument("--output-dir", help="Directory to save JSON reports")
    watch_parser.add_argument("--min-score", type=int, help="Alert if score below threshold")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "watch":
        watch(
            folder=args.folder,
            interval=args.interval,
            lang=args.lang,
            webhook=args.webhook,
            output_dir=args.output_dir,
            min_score=args.min_score,
        )


if __name__ == "__main__":
    main()
