# Diagnostic script to check Supabase Storage bucket and upload permissions
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client  # type: ignore

url = os.getenv("SUPABASE_URL")
sr = os.getenv("SUPABASE_SERVICE_ROLE") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
anon = os.getenv("SUPABASE_ANON_KEY")
key = sr or anon
bucket = os.getenv("SUPABASE_BUCKET", "podcasts")

key_src = "SERVICE_ROLE" if sr else ("ANON" if anon else "NONE")
print(f"URL set: {bool(url)}  Key set: {bool(key)} ({key_src})  Bucket: {bucket}")
if not url or not key:
    raise SystemExit("Missing SUPABASE_URL or key in .env")

client = create_client(url, key)
print("Client OK")

# List buckets
try:
    buckets = client.storage.list_buckets() or []
    print("Buckets:", [b.get("name") for b in buckets])
except Exception as ex:
    print("List buckets failed:", ex)

# Ensure bucket exists
try:
    names = {b.get("name") for b in (buckets or [])}
    if bucket not in names:
        print(f"Bucket '{bucket}' not found. Please create it in the Supabase dashboard or set SUPABASE_BUCKET to an existing bucket.")
    else:
        print(f"Bucket '{bucket}' exists.")
except Exception as ex:
    print("List/verify bucket failed:", ex)

# Test upload
try:
    test_path = Path(".tmp_supabase_upload_test.txt")
    test_path.write_text(f"upload test at {datetime.now().isoformat()}", encoding="utf-8")
    with open(test_path, "rb") as f:
        client.storage.from_(bucket).upload(
            "diagnostics/.tmp_supabase_upload_test.txt",
            f,
            file_options={"content-type": "text/plain; charset=utf-8", "upsert": "true", "x-upsert": "true"},
        )
    print("Test upload OK")
except Exception as ex:
    print("Test upload failed:", ex)
finally:
    try:
        test_path.unlink(missing_ok=True)
    except Exception:
        pass
