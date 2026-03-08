#!/usr/bin/env python3
"""
Quick setup verification for HA Documentation Generator
Run this to verify everything is configured correctly
"""

import yaml
import os
import sys

def check_config_file():
    """Check if config file exists and is valid"""
    config_path = "/config/scripts/ha_docs/config.yaml"
    
    if not os.path.exists(config_path):
        print("âŒ Config file not found at:", config_path)
        print("   Create it from config_production.yaml.example")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check required fields
        required = [
            ('bookstack', 'url'),
            ('bookstack', 'token_id'),
            ('bookstack', 'token_secret'),
            ('bookstack', 'book_id'),
            ('homeassistant', 'url'),
            ('homeassistant', 'token')
        ]
        
        missing = []
        for section, key in required:
            if section not in config or key not in config[section]:
                missing.append(f"{section}.{key}")
            elif not config[section][key] or 'your_' in str(config[section][key]):
                missing.append(f"{section}.{key} (not configured)")
        
        if missing:
            print("âŒ Config file incomplete. Missing:")
            for item in missing:
                print(f"   - {item}")
            return False
        
        print("âœ… Config file looks good")
        return True
        
    except Exception as e:
        print(f"âŒ Error reading config: {e}")
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    try:
        import requests
        print("âœ… requests library installed")
    except ImportError:
        print("âŒ requests library not installed")
        print("   Run: pip install requests --break-system-packages")
        return False
    
    try:
        import yaml
        print("âœ… yaml library installed")
    except ImportError:
        print("âŒ yaml library not installed")
        print("   Run: pip install pyyaml --break-system-packages")
        return False
    
    return True

def check_script_file():
    """Check if main script exists"""
    script_path = "/config/scripts/ha_docs/ha_docs_production.py"
    
    if not os.path.exists(script_path):
        print(f"âŒ Main script not found at: {script_path}")
        return False
    
    print("âœ… Main script found")
    return True

def check_permissions():
    """Check if script is executable"""
    script_path = "/config/scripts/ha_docs/ha_docs_production.py"
    
    if os.path.exists(script_path):
        if os.access(script_path, os.R_OK):
            print("âœ… Script is readable")
        else:
            print("âŒ Script is not readable")
            return False
    
    return True

def test_bookstack_connection():
    """Test BookStack API connection"""
    try:
        import requests
        config_path = "/config/scripts/ha_docs/config.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        url = f"{config['bookstack']['url']}/api/books"
        headers = {
            'Authorization': f"Token {config['bookstack']['token_id']}:{config['bookstack']['token_secret']}"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            books = response.json().get('data', [])
            print(f"âœ… BookStack connection successful ({len(books)} books found)")
            
            # Check if configured book exists
            book_id = config['bookstack']['book_id']
            book_exists = any(b['id'] == book_id for b in books)
            
            if book_exists:
                print(f"âœ… Configured book (ID: {book_id}) exists")
            else:
                print(f"âš ï¸  Configured book (ID: {book_id}) not found")
                print("   Available books:")
                for book in books:
                    print(f"   - ID {book['id']}: {book['name']}")
            
            return True
        else:
            print(f"âŒ BookStack connection failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"âŒ BookStack connection error: {e}")
        return False

def test_ha_connection():
    """Test Home Assistant API connection"""
    try:
        import requests
        config_path = "/config/scripts/ha_docs/config.yaml"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        url = f"{config['homeassistant']['url']}/api/"
        headers = {
            'Authorization': f"Bearer {config['homeassistant']['token']}"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"âœ… Home Assistant connection successful")
            print(f"   Message: {data.get('message', 'API running')}")
            return True
        else:
            print(f"âŒ Home Assistant connection failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"âŒ Home Assistant connection error: {e}")
        return False

def main():
    print("=" * 60)
    print("HA Documentation Generator - Setup Verification")
    print("=" * 60)
    print()
    
    checks = []
    
    print("ðŸ“ Checking file structure...")
    checks.append(check_script_file())
    checks.append(check_config_file())
    checks.append(check_permissions())
    print()
    
    print("ðŸ“¦ Checking dependencies...")
    checks.append(check_dependencies())
    print()
    
    print("ðŸ”Œ Testing connections...")
    checks.append(test_bookstack_connection())
    checks.append(test_ha_connection())
    print()
    
    print("=" * 60)
    if all(checks):
        print("âœ… All checks passed! You're ready to run the generator.")
        print()
        print("Next steps:")
        print("1. Test: python3 /config/scripts/ha_docs/ha_docs_production.py --config /config/scripts/ha_docs/config.yaml --test")
        print("2. Run: python3 /config/scripts/ha_docs/ha_docs_production.py --config /config/scripts/ha_docs/config.yaml")
        print("3. Add shell_command to configuration.yaml")
        print("4. Create automation for scheduled updates")
    else:
        print("âŒ Some checks failed. Please fix the issues above.")
        sys.exit(1)
    print("=" * 60)

if __name__ == '__main__':
    main()