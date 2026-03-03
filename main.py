
import sys, traceback, os, smtplib
from email.message import EmailMessage
print("=" * 60)
MAIL_FROM = os.environ.get("MAIL_FROM", "")
MAIL_TO   = os.environ.get("MAIL_TO",   "")
MAIL_PASS = os.environ.get("MAIL_PASS", "")
print(f"MAIL_FROM : {'SET (' + MAIL_FROM[:4] + '***)' if MAIL_FROM else '*** BOŞ ***'}")
print(f"MAIL_TO   : {'SET (' + MAIL_TO[:4]   + '***)' if MAIL_TO   else '*** BOŞ ***'}")
print(f"MAIL_PASS : {'SET (' + str(len(MAIL_PASS)) + ' karakter)' if MAIL_PASS else '*** BOŞ ***'}")
if not all([MAIL_FROM, MAIL_TO, MAIL_PASS]):
    print("HATA: secret eksik!"); sys.exit(1)
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.login(MAIL_FROM, MAIL_PASS)
        msg = EmailMessage()
        msg["Subject"] = "Actions Test"
        msg["From"] = MAIL_FROM
        msg["To"] = MAIL_TO
        msg.set_content("Test maili - GitHub Actions calisiyor!")
        s.send_message(msg)
    print("BASARILI - Mail gonderildi!")
except Exception as e:
    print(f"HATA: {e}")
    traceback.print_exc()
    sys.exit(1)



