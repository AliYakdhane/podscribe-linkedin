#!/usr/bin/env python3
"""
Emergency recovery script to restore our work
"""

import subprocess
import sys

def run_command(cmd):
    """Run a git command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

def main():
    print("🚨 EMERGENCY RECOVERY - Restoring our work...")
    
    # Check current status
    print("\n1. Checking current git status...")
    stdout, stderr = run_command("git status")
    print(stdout)
    
    # Check commit history
    print("\n2. Checking commit history...")
    stdout, stderr = run_command("git log --oneline -5")
    print(stdout)
    
    # Check reflog
    print("\n3. Checking reflog...")
    stdout, stderr = run_command("git reflog -5")
    print(stdout)
    
    print("\n🔧 RECOVERY OPTIONS:")
    print("1. Run: git checkout 591cd5b -- src/session_manager.py")
    print("2. Run: git checkout 591cd5b -- src/content_generator.py") 
    print("3. Run: git checkout 591cd5b -- streamlit_app.py")
    print("4. Or: git reset --hard HEAD@{1} (from reflog)")

if __name__ == "__main__":
    main()
