"""
Wekelijkse audit e-mail — draait via GitHub Actions op maandag 08:00 UTC.

Stuurt per tenant een samenvatting van de afgelopen 7 dagen:
  - aantal logins
  - aantal sluitingen
  - aantal verzonden bestellingen
  - aantal nieuwe gebruikers
  - aantal nieuwe tenants (alleen zichtbaar voor platform-tenant)

Vereiste omgevingsvariabelen (GitHub Secrets):
  SUPABASE_URL          — project URL
  SUPABASE_SERVICE_KEY  — service_role key (bypast RLS)
  RESEND_API_KEY        — Resend API key
  RESEND_DOMEIN_GEVERIFIEERD — "true" als eigen domein geverifieerd is
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import resend
from supabase import Client, create_client


def _supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _laad_actieve_tenants(sb: Client) -> list[dict]:
    resp = sb.table("tenants").select("id, name, slug").eq("status", "active").execute()
    return resp.data or []


def _laad_audit_events(sb: Client, tenant_id: str, sinds_iso: str) -> list[dict]:
    resp = (
        sb.table("audit_log")
        .select("actie, user_naam, details, created_at")
        .eq("tenant_id", tenant_id)
        .gte("created_at", sinds_iso)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


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


def _tel_acties(events: list[dict]) -> Counter:
    return Counter(e["actie"] for e in events)


def _unieke_gebruikers(events: list[dict]) -> set[str]:
    return {e["user_naam"] for e in events if e.get("actie") == "login"}


def _html_audit(
    restaurant_naam: str,
    periode_start:   str,
    periode_eind:    str,
    acties:          Counter,
    unieke_users:    set[str],
    recente_events:  list[dict],
) -> str:
    rij_html = []
    for actie, aantal in sorted(acties.items(), key=lambda x: (-x[1], x[0])):
        rij_html.append(
            f'<tr>'
            f'<td style="padding:8px;border:1px solid #CBD5E1">{actie}</td>'
            f'<td style="padding:8px;border:1px solid #CBD5E1;text-align:right">{aantal}</td>'
            f'</tr>'
        )
    tabel_rijen = "\n".join(rij_html) or (
        '<tr><td colspan="2" style="padding:8px;border:1px solid #CBD5E1;color:#6B7280">'
        'Geen activiteit in deze periode.'
        '</td></tr>'
    )

    recent_html = []
    for e in recente_events[:10]:
        tijd = e["created_at"][:16].replace("T", " ")
        recent_html.append(
            f'<li style="margin:4px 0">'
            f'<code style="color:#2E5AAC">{tijd}</code> — '
            f'<strong>{e["user_naam"]}</strong>: {e["actie"]}'
            f'</li>'
        )
    recent_lijst = "\n".join(recent_html) or '<li style="color:#6B7280">Geen events.</li>'

    return f"""
<html><body style="font-family:sans-serif;color:#111827;max-width:640px;margin:0 auto">
<h2 style="color:#2E5AAC">Wekelijkse audit — {restaurant_naam}</h2>
<p>Samenvatting van activiteit tussen <strong>{periode_start}</strong> en <strong>{periode_eind}</strong>.</p>

<h3 style="margin-top:24px">Aantal acties per soort</h3>
<table style="border-collapse:collapse;width:100%;margin:12px 0">
  <tr>
    <th style="padding:8px;border:1px solid #CBD5E1;text-align:left;background:#F3F4F6">Actie</th>
    <th style="padding:8px;border:1px solid #CBD5E1;text-align:right;background:#F3F4F6">Aantal</th>
  </tr>
  {tabel_rijen}
</table>

<p><strong>Unieke ingelogde gebruikers:</strong> {len(unieke_users)}</p>

<h3 style="margin-top:24px">Laatste 10 events</h3>
<ul style="padding-left:18px">
  {recent_lijst}
</ul>

<p style="color:#6B7280;font-size:0.85rem;margin-top:24px">
  Log in op de Besteltool voor de volledige audit-log.
</p>
</body></html>"""


def main() -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]
    domein_ok = os.getenv("RESEND_DOMEIN_GEVERIFIEERD", "false").lower() == "true"
    afzender  = "no-reply@besteltool.nl" if domein_ok else "onboarding@resend.dev"

    sb             = _supabase()
    nu             = datetime.now(timezone.utc)
    week_geleden   = nu - timedelta(days=7)
    sinds_iso      = week_geleden.isoformat()
    periode_start  = week_geleden.strftime("%d %b %Y")
    periode_eind   = nu.strftime("%d %b %Y")

    tenants = _laad_actieve_tenants(sb)
    if not tenants:
        print("Geen actieve tenants gevonden.")
        return

    fouten = 0
    for tenant in tenants:
        tenant_id = tenant["id"]
        naam      = tenant["name"]

        events = _laad_audit_events(sb, tenant_id, sinds_iso)
        if not events:
            print(f"[{naam}] Geen activiteit afgelopen week — overgeslagen.")
            continue

        adressen = _laad_manager_emails(sb, tenant_id)
        if not adressen:
            print(f"[{naam}] Geen manager-email — overgeslagen.")
            continue

        acties       = _tel_acties(events)
        unieke_users = _unieke_gebruikers(events)
        html         = _html_audit(naam, periode_start, periode_eind,
                                    acties, unieke_users, events)

        try:
            resend.Emails.send({
                "from":    afzender,
                "to":      adressen,
                "subject": f"Wekelijkse audit ({periode_start} — {periode_eind}) — {naam}",
                "html":    html,
            })
            print(f"[{naam}] Audit e-mail verzonden naar {adressen} "
                  f"({sum(acties.values())} events)")
        except Exception as e:
            print(f"[{naam}] FOUT bij verzenden: {e}", file=sys.stderr)
            fouten += 1

    sys.exit(1 if fouten else 0)


if __name__ == "__main__":
    main()
