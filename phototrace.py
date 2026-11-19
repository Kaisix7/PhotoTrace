
import argparse
import json
from pathlib import Path
from typing import Any

from phototrace_app.analysis import analyze_image
from phototrace_app.reports import save_report


def display_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 45)
    print("             PHOTOTRACE v2.0.0")
    print("=" * 45)

    print(f"\nFile: {report['original_filename']}")
    print(f"Size: {report['file']['size_bytes']} bytes")
    print(f"Metadata fields: {report['summary']['metadata_field_count']}")
    gps = report["gps"]
    print("\n[ GPS ]")
    if gps["status"] == "valid":
        print("Latitude:", gps["latitude"])
        print("Longitude:", gps["longitude"])
        print("Altitude:", gps["altitude"] or "Not available")
    else:
        print(gps["message"])
    print("\n[ INTEGRITY FINDINGS ]")
    for finding in report["integrity_findings"]:
        print(f"[{finding['severity'].upper()}] {finding['title']}")
        print(f"  {finding['explanation']}")
    print("\n" + "=" * 45)


def main():
    parser = argparse.ArgumentParser(
        description="PhotoTrace EXIF and GPS Analyzer"
    )

    parser.add_argument("image", help="Path to a local image")
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory for the generated JSON report (default: reports)",
    )
    args = parser.parse_args()

    image_path = Path(args.image).expanduser()

    if not image_path.is_file():
        parser.error(f"File not found: {image_path}")

    try:
        report = analyze_image(image_path)
        display_report(report)
        report_path = save_report(report, Path(args.reports_dir))
        print(f"\nReport saved: {report_path.resolve()}")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
