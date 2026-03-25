#!/usr/bin/env python3
"""
Setup verification for HA Documentation Generator.
Run this before using ha_docs_production.py to confirm everything is in order.

Usage:
    python3 verify_setup.py --config config.yaml
"""

import yaml
import os
import sys
import argparse


def check_files(config_path: str) -> bool:
    """Check script and config file exist and are readable"""
    ok = True

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ha_docs_production.py')
    if os.path.exists(script_path):
        print("  OK  Main script found")
    else:
        print("  --  Main script not found:", script_path)
        ok = False

    if not os.path.exists(config_path):
        print("  --  Config file not found:", config_path)
        print("      Copy config.yaml.example to config.yaml and fill in your details")
        return False

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print("  --  Error reading config:", e)
        return False

    # Required fields (book_id intentionally excluded — null is valid)
    required = [
        ('bookstack', 'url'),
        ('bookstack', 'token_id'),
        ('bookstack', 'token_secret'),
        ('homeassistant', 'url'),
        ('homeassistant', 'token'),
    ]

    missing = []
    for section, key in required:
        val = config.get(section, {}).get(key)
        if not val or str(val).startswith('YOUR_'):
            missing.append(f"{section}.{key}")

    if missing:
        print("  --  Config file incomplete. Missing:")
        for item in missing:
            print(f"       - {item}")
        ok = False
    else:
        print("  OK  Config file looks good")

    if os.access(config_path, os.R_OK):
        print("  OK  Script is readable")
    else:
        print("  --  Script is not readable")
        ok = False

    return ok


def check_dependencies() -> bool:
    """Check required Python packages"""
    ok = True
    try:
        import requests  # noqa: F401
        print("  OK  requests library installed")
    except ImportError:
        print("  --  requests library not installed")
        print("      Run: pip install requests --break-system-packages")
        ok = False

    try:
        import yaml  # noqa: F401
        print("  OK  yaml library installed")
    except ImportError:
        print("  --  yaml library not installed")
        print("      Run: pip install pyyaml --break-system-packages")
        ok = False

    return ok


def test_bookstack(config_path: str) -> bool:
    """Test BookStack API connection"""
    try:
        import requests

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        url = config['bookstack']['url'].rstrip('/') + '/api/books'
        headers = {
            'Authorization': f"Token {config['bookstack']['token_id']}:{config['bookstack']['token_secret']}"
        }

        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            books = response.json().get('data', [])
            print(f"  OK  BookStack connection successful ({len(books)} books found)")

            book_id = config['bookstack'].get('book_id')
            book_name = config['bookstack'].get('book_name', 'Home Assistant Documentation')

            if book_id:
                if any(b['id'] == book_id for b in books):
                    print(f"  OK  Configured book (ID: {book_id}) exists")
                else:
                    print(f"  --  Configured book (ID: {book_id}) not found")
                    print("      Available books:")
                    for book in books:
                        print(f"       - ID {book['id']}: {book['name']}")
            else:
                match = next((b for b in books if b['name'] == book_name), None)
                if match:
                    print(f"  OK  Book '{book_name}' found (ID: {match['id']})")
                    print(f"      Tip: set book_id: {match['id']} in config.yaml to skip name lookup")
                else:
                    print(f"  OK  Book '{book_name}' not found — will be created on first run")

            return True
        else:
            print(f"  --  BookStack connection failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"  --  BookStack connection error: {e}")
        return False


def test_ha(config_path: str) -> bool:
    """Test Home Assistant API connection"""
    try:
        import requests

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        url = config['homeassistant']['url'].rstrip('/') + '/api/'
        headers = {'Authorization': f"Bearer {config['homeassistant']['token']}"}

        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print(f"  OK  Home Assistant connection successful")
            print(f"      Message: {data.get('message', 'API running.')}")
            return True
        else:
            print(f"  --  Home Assistant connection failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"  --  Home Assistant connection error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Verify HA Documentation Generator setup')
    parser.add_argument('--config', default='config.yaml', help='Path to config YAML file')
    args = parser.parse_args()

    print("=" * 60)
    print("HA Documentation Generator - Setup Verification")
    print("=" * 60)

    results = []

    print("\nChecking file structure...")
    results.append(check_files(args.config))

    print("\nChecking dependencies...")
    results.append(check_dependencies())

    print("\nTesting connections...")
    results.append(test_bookstack(args.config))
    results.append(test_ha(args.config))

    print("\n" + "=" * 60)
    if all(results):
        print("All checks passed. Ready to run the generator.")
        print()
        print("Next steps:")
        print(f"  Test:  python3 ha_docs_production.py --config {args.config} --test")
        print(f"  Run:   python3 ha_docs_production.py --config {args.config}")
    else:
        print("Some checks failed. Please fix the issues above.")
        sys.exit(1)
    print("=" * 60)


if __name__ == '__main__':
    main()
