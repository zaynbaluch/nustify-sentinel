import os
import smtplib
from email.message import EmailMessage
from core.db import supabase

def send_alert(title, summary, url):
    subs = supabase.table("email_subscribers").select("email").execute().data
    if not subs:
        return

    if isinstance(summary, list):
        plain = "\n".join(f"• {s}" for s in summary)
        html = "<ul>" + "".join(f"<li>{s}</li>" for s in summary) + "</ul>"
    else:
        plain = str(summary)
        html = plain.replace("\n", "<br>")

    # 🔹 URL ADDITION (plain + html)
    if url:
        plain += f"\n\nPage link:\n{url}"
        html += f'<br><br><a href="{url}" target="_blank">{url}</a>'

    msg = EmailMessage()
    msg["Subject"] = f"🚨 NUSTIFY-SENTINEL Alert: {title}"
    msg["From"] = os.getenv("SENDER_EMAIL")
    msg["To"] = ", ".join(s["email"] for s in subs)
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP_SSL(
        os.getenv("SMTP_SERVER"),
        int(os.getenv("SMTP_PORT"))
    ) as smtp:
        smtp.login(
            os.getenv("SENDER_EMAIL"),
            os.getenv("SENDER_PASSWORD")
        )
        smtp.send_message(msg)
