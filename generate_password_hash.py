#!/usr/bin/env python3
"""
Simple script to generate a secure password hash for the Streamlit app.
Run this script to generate a hash for your desired password.
"""

import hashlib
import getpass

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

if __name__ == "__main__":
    print("🔐 Password Hash Generator for Streamlit App")
    print("=" * 50)
    
    # Get password from user
    password = getpass.getpass("Enter your desired password: ")
    
    if not password:
        print("❌ No password entered. Exiting.")
        exit(1)
    
    # Generate hash
    password_hash = hash_password(password)
    
    print("\n✅ Password hash generated successfully!")
    print(f"Password: {password}")
    print(f"Hash: {password_hash}")
    print("\n📋 Copy this hash to your streamlit_app.py file:")
    print(f'ADMIN_PASSWORD_HASH = "{password_hash}"')
    print("\n🔒 Keep your password secure and don't share it!")
