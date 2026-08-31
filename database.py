import os
from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Database credentials not found in .env")


def create_public_client() -> Client:
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=SyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def create_authenticated_client(access_token, refresh_token):
    client = create_public_client()
    auth_response = client.auth.set_session(access_token, refresh_token)
    return client, auth_response.session


def get_admin_client() -> Client:
    if not SUPABASE_SECRET_KEY:
        raise ValueError("SUPABASE_SECRET_KEY cannot be found in the environment.")

    return create_client(
        SUPABASE_URL,
        SUPABASE_SECRET_KEY,
        options=SyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


# Public, unauthenticated client used only for data covered by public RLS policies.
supabase: Client = create_public_client()
