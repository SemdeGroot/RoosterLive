# core/utils/emails/email_dienstenoverzicht.py
from __future__ import annotations

import os
from datetime import date

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.text import capfirst
from email.mime.image import MIMEImage


# Mail-safe, lichte tinten (werken in light & dark mail clients)
ROW_BG = {
    "green": "#EAF7F0",
    "red":   "#FDEDED",
    "blue":  "#EEF4FF",
}
NEUTRAL_BG = "#FFFFFF"


def _fmt_weekday(d: date) -> str:
    return capfirst(date_format(d, "D"))


def _fmt_dm(d: date) -> str:
    return date_format(d, "d-m")

def send_diensten_overzicht_email(
    *,
    to_email: str,
    first_name: str,
    header_title: str,
    monday: date,
    week_end: date,
    rows: list[dict],
    location_rows: list[dict],
):
    """
    rows verwacht:
      - date (date OF iso-string "YYYY-MM-DD")
      - show_day (bool)
      - period_label, period_time (str)
      - location, task (str)
      - row_bg (str, optional) -> bv "#EEF4FF"
      - is_assigned (bool, optional) -> True bij echte shift
    location_rows verwacht:
      - name, address (str)
      - row_bg (str, optional)
    """
    if not to_email:
        return

    translation.activate("nl")

    display_name_raw = (first_name or "").strip().capitalize() or "Collega"
    display_name = escape(display_name_raw)

    header_title_raw = header_title or ""
    header_title_esc = escape(header_title_raw)

    subject = f"Dienstenoverzicht voor {header_title_raw}"
    from_email = settings.DEFAULT_FROM_EMAIL
    logo_path = os.path.join(settings.BASE_DIR, "core", "static", "img", "app_icon_trans-512x512.png")

    def td_text(v: str) -> str:
        v = (v or "").strip()
        return escape(v) if v else '<span style="color:#9aa3af;">—</span>'

    def small_text(v: str) -> str:
        return escape((v or "").strip())

    # ========== Diensten tabel rows ==========
    body_rows_html: list[str] = []
    for r in rows:
        d_raw = r["date"]
        d = d_raw if isinstance(d_raw, date) else date.fromisoformat(d_raw)

        is_assigned = bool(r.get("is_assigned", True))  # default True voor backwards compat
        bg = (r.get("row_bg") or "").strip()

        # Alleen tinten als er een shift is
        row_bg = bg if (bg and is_assigned) else NEUTRAL_BG

        if r.get("show_day"):
            day_cell = f"""
              <div style="line-height:1.2;">
                <strong>{escape(_fmt_weekday(d))}</strong><br>
                <small style="color:#6b7280;">{escape(_fmt_dm(d))}</small>
              </div>
            """
        else:
            day_cell = '<span aria-hidden="true">&nbsp;</span>'

        period_cell = f"""
          <div style="line-height:1.2;">
            <strong>{small_text(r.get("period_label",""))}</strong><br>
            <small style="color:#6b7280;">{small_text(r.get("period_time",""))}</small>
          </div>
        """

        body_rows_html.append(f"""
          <tr style="background:{row_bg};">
            <td style="padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top; width:90px;">
              {day_cell}
            </td>
            <td style="padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top; width:130px;">
              {period_cell}
            </td>
            <td style="padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top;">
              {td_text(r.get("location",""))}
            </td>
            <td style="padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top;">
              {td_text(r.get("task",""))}
            </td>
          </tr>
        """)

    diensten_table_html = f"""
      <div style="margin:12px 0 16px;">
        <div style="color:#6b7280; margin:0 0 10px;">
          {escape(date_format(monday, "d-m-Y"))} – {escape(date_format(week_end, "d-m-Y"))}
        </div>

        <div style="overflow-x:auto; -webkit-overflow-scrolling:touch;">
          <table style="
              min-width: 620px;
              width: 100%;
              border-collapse: collapse;
              border: 1px solid #e5e7eb;
              border-radius: 12px;
              overflow: hidden;
              table-layout: fixed;
            ">
            <thead>
              <tr style="background:#f8fafc;">
                <th style="text-align:left; padding:10px; border-bottom:1px solid #e5e7eb; width:90px;">Dag</th>
                <th style="text-align:left; padding:10px; border-bottom:1px solid #e5e7eb; width:130px;">Dagdeel</th>
                <th style="text-align:left; padding:10px; border-bottom:1px solid #e5e7eb;">Locatie</th>
                <th style="text-align:left; padding:10px; border-bottom:1px solid #e5e7eb;">Taak</th>
              </tr>
            </thead>
            <tbody style="word-break:break-word; overflow-wrap:anywhere;">
              {''.join(body_rows_html)}
            </tbody>
          </table>
        </div>
      </div>
    """

    # ========== Adressen tabel ==========
    addr_rows_html: list[str] = []
    for loc in location_rows:
        bg = (loc.get("row_bg") or "").strip()
        row_bg = bg if bg else NEUTRAL_BG
        addr_rows_html.append(f"""
          <tr style="background:{row_bg};">
            <td style="padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top; width:180px;">
              {td_text(loc.get("name",""))}
            </td>
            <td style="padding:10px; border-bottom:1px solid #e5e7eb; vertical-align:top;">
              {td_text(loc.get("address",""))}
            </td>
          </tr>
        """)

    adressen_html = ""
    if location_rows:
        adressen_html = f"""
          <div style="margin-top:16px;">
            <div style="font-weight:700; margin:0 0 10px;">Adressen</div>

            <div style="overflow-x:auto; -webkit-overflow-scrolling:touch;">
              <table style="
                  min-width: 520px;
                  width: 100%;
                  border-collapse: collapse;
                  border: 1px solid #e5e7eb;
                  border-radius: 12px;
                  overflow: hidden;
                  table-layout: fixed;
                ">
                <thead>
                  <tr style="background:#f8fafc;">
                    <th style="text-align:left; padding:10px; border-bottom:1px solid #e5e7eb; width:180px;">Locatie</th>
                    <th style="text-align:left; padding:10px; border-bottom:1px solid #e5e7eb;">Adres</th>
                  </tr>
                </thead>
                <tbody style="word-break:break-word; overflow-wrap:anywhere;">
                  {''.join(addr_rows_html)}
                </tbody>
              </table>
            </div>
          </div>
        """

    html_body = f"""
      <p style="margin:0 0 18px 0;">Beste {display_name},</p>

      <p style="margin:0 0 12px 0;">
        Hieronder vind je jouw dienstenoverzicht voor <strong>{header_title_esc}</strong>.
      </p>

      {diensten_table_html}
      {adressen_html}

      <p style="margin:18px 0 0;">Fijn weekend!</p>

      <p style="margin:24px 0 12px 0;">
        Met vriendelijke groet,<br>
        Het Apotheek Jansen Team
      </p>
    """

    footer_text = (
        'U ontvangt deze e-mail omdat er voor u diensten zijn ingepland voor de komende week. '
        'U kunt deze e-mailmeldingen uitschakelen via het tabblad '
        '<a href="https://app.apotheekjansen.com/profiel" style="text-decoration:underline;">Profiel</a> '
        'in de Jansen App.'
    )

    context = {"content": html_body, "footer_text": footer_text}
    html_content = render_to_string("includes/mail_base.html", context)

    text_content = (
        f"Beste {display_name_raw},\n\n"
        f"Dienstenoverzicht voor {header_title_raw} ({date_format(monday,'d-m-Y')} – {date_format(week_end,'d-m-Y')}).\n"
        "Open de app om het volledige overzicht te bekijken.\n\n"
        "Fijn weekend!\n"
        "Het Apotheek Jansen Team"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")

    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            image = MIMEImage(f.read())
        image.add_header("Content-ID", "<logo>")
        image.add_header("Content-Disposition", "inline", filename="logo.png")
        msg.attach(image)

    msg.send()