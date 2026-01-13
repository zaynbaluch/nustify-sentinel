import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing in environment")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing in environment")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
