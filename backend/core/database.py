from __future__ import annotations
from supabase import create_client, Client
from .config import settings


def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_anon_key)


def get_supabase_admin() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_for_user(token: str) -> Client:
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return client
