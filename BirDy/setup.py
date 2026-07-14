import subprocess
import sys

print("Installing BirDy Core Dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Initializing Neural Vision (Playwright)...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

print("\n" + "="*40)
print("✅ BirDy INFRASTRUCTURE READY")
print("🚀 COMMAND: python ignition.py")
print("="*40 + "\n")
