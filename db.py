"""Supabase database client — centrale toegang tot alle persistente data."""
from __future__ import annotations
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    """Geeft een gecachte Supabase client terug."""
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)
