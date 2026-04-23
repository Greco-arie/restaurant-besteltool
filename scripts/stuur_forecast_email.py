"""
Dagelijkse forecast e-mail — draait via GitHub Actions om 22:00 UTC.

Vereiste omgevingsvariabelen (GitHub Secrets):
  SUPABASE_URL       — project URL
  SUPABASE_SERVICE_KEY — service_role key (bypassed RLS, alleen voor scripts)
  RESEND_API_KEY     — Resend API key
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import resend
from supabase import create_client, Client


def _supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _laad_actieve_tenants(sb: Client) -> list[dict]:
    resp = sb.table("tenants").select("id, name, slug").eq("status", "active").execute()
    return resp.data or []


def _laad_forecast_morgen(sb: Client, tenant_id: str, datum_morgen: str) -> int | None:
    resp = (
        sb.table("forecast_log")
        .select("predicted_covers")
        .eq("tenant_id", tenant_id)
        .eq("datum", datum_morgen)
        .execute()
    )
    if resp.data:
        return int(resp.data[0]["predicted_covers"])
    return None


def _laad_manager_emails(sb: Client, tenant_id: str) -> list[str]:
    resp = (
        sb.table("tenant_users")
        .select("email")
        .eq("tenant_id", tenant_id)
        .in_("role", ["manager", "admin"])
        .eq("is_active", True)
        .execute()
    )
    return [r["email"] for r in (resp.data or []) if r.get("email")]


def _html_forecast(
    restaurant_naam: str,
    datum_morgen: str,
    weekdag: str,
    predicted_covers: int,
) -> str:
    return f"""
<html><body style="font-family:sans-serif;color:#111827;max-width:560px;margin:0 auto">
<h2 style="color:#2E5AAC">Forecast morgen — {restaurant_naam}</h2>
<p>Goedenavond,</p>
<p>Hier is de forecast voor <strong>{weekdag} {datum_morgen}</strong>:</p>
<table style="border-collapse:collapse;width:100%;margin:16px 0">
  <tr>
    <td style="padding:12px;border:1px solid #CBD5E1;font-weight:600">Verwachte bonnen</td>
    <td style="padding:12px;border:1px solid #CBD5E1;font-size:1.4rem;font-weight:700;
               color:#2E5AAC">{predicted_covers}</td>
  </tr>
</table>
<p style="color:#6B7280;font-size:0.85rem">
  Log in op de Besteltool om het besteladvies te bekijken en bestellingen te versturen.
</p>
</body></html>"""


WEEKDAGEN_NL = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def main() -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]
    domein_ok = os.getenv("RESEND_DOMEIN_GEVERIFIEERD", "false").lower() == "true"
    afzender  = "no-reply@besteltool.nl" if domein_ok else "onboarding@resend.dev"

    sb            = _supabase()
    datum_morgen  = (date.today() + timedelta(days=1)).isoformat()
    weekdag       = WEEKDAGEN_NL[(date.today() + timedelta(days=1)).weekday()]

    tenants = _laad_actieve_tenants(sb)
    if not tenants:
        print("Geen actieve tenants gevonden.")
        return

    fouten = 0
    for tenant in tenants:
        tenant_id   = tenant["id"]
        naam        = tenant["name"]
        predicted   = _laad_forecast_morgen(sb, tenant_id, datum_morgen)

        if predicted is None:
            print(f"[{naam}] Geen forecast voor morgen — overgeslagen.")
            continue

        adressen = _laad_manager_emails(sb, tenant_id)
        if not adressen:
            print(f"[{naam}] Geen manager-email — overgeslagen.")
            continue

        html = _html_forecast(naam, datum_morgen, weekdag, predicted)
        try:
            resend.Emails.send({
                "from":    afzender,
                "to":      adressen,
                "subject": f"Forecast morgen ({weekdag}) — {naam}",
                "html":    html,
            })
            print(f"[{naam}] Forecast e-mail verzonden naar {adressen} ({predicted} bonnen)")
        except Exception as e:
            print(f"[{naam}] FOUT bij verzenden: {e}", file=sys.stderr)
            fouten += 1

    sys.exit(1 if fouten else 0)


if __name__ == "__main__":
    main()
