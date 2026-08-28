#!/usr/bin/env python3
"""Check pytest skips against allowed list."""

import sys
import xml.etree.ElementTree as ET


def load_allowed_skips(allowed_file):
    """Load allowed skips from a file."""
    allowed = set()
    if not allowed_file:
        return allowed
    try:
        with open(allowed_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) >= 1:
                    allowed.add(parts[0].strip())
    except FileNotFoundError:
        pass
    return allowed


def parse_junit_xml(xml_file):
    """Parse JUnit XML and extract skipped tests."""
    skipped = []
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for testcase in root.iter('testcase'):
            skip = testcase.find('skipped')
            if skip is not None:
                class_name = testcase.get('classname', '')
                name = testcase.get('name', '')
                reason = skip.get('message', skip.text or '')
                full_name = f"{class_name}.{name}" if class_name else name
                skipped.append((full_name, reason.strip()))
    except Exception as e:
        print(f"Error parsing JUnit XML: {e}", file=sys.stderr)
        sys.exit(1)
    return skipped


def main():
    if len(sys.argv) < 2:
        print("Usage: check-pytest-skips.py <junit-xml> [allowed-skips-file]")
        sys.exit(1)

    xml_file = sys.argv[1]
    allowed_file = sys.argv[2] if len(sys.argv) > 2 else None

    allowed_skips = load_allowed_skips(allowed_file)
    skipped_tests = parse_junit_xml(xml_file)

    if not skipped_tests:
        print("OK: No skipped tests")
        sys.exit(0)

    print(f"Found {len(skipped_tests)} skipped tests:")
    print("-" * 60)

    allowed_count = 0
    not_allowed_count = 0
    not_allowed_list = []

    for full_name, reason in skipped_tests:
        if full_name in allowed_skips:
            print(f"ALLOWED: {full_name} - {reason}")
            allowed_count += 1
        else:
            print(f"NOT ALLOWED: {full_name} - {reason}")
            not_allowed_count += 1
            not_allowed_list.append((full_name, reason))

    print("-" * 60)
    print(f"Allowed: {allowed_count}, Not allowed: {not_allowed_count}")

    if not_allowed_count > 0:
        print("\nERROR: Found tests skipped without valid reason")
        for full_name, reason in not_allowed_list:
            print(f"  - {full_name}: {reason}")
        sys.exit(1)

    print("\nOK: All skipped tests are in the allowed list")
    sys.exit(0)


if __name__ == '__main__':
    main()
