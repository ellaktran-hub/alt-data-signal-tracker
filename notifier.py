"""
notifier.py
Email alerts for the AltData pipeline.
Requires: project/.gmail_password  (gitignored — 16-char Gmail App Password, no spaces)
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

GMAIL_USER  = "ellaktran@gmail.com"
ALERT_TO    = "ellaktran@gmail.com"
_PW_FILE    = Path(__file__).parent / ".gmail_password"
_DASHBOARD  = "https://alt-data-signal-tracker-avsrd4vrbxve9yfcyelj6q.streamlit.app/"


def _load_password():
    if not _PW_FILE.exists():
        return None
    pw = _PW_FILE.read_text().strip().replace(" ", "")
    return pw or None


def send_email(subject, body):
    """Send plain-text email via Gmail SMTP SSL. Returns True on success."""
    password = _load_password()
    if not password:
        print("[notifier] Skipping — no .gmail_password file. See CLAUDE.md to enable alerts.")
        return False

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = ALERT_TO
    msg.attach(MIMEText(body, "plain"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
            srv.login(GMAIL_USER, password)
            srv.sendmail(GMAIL_USER, ALERT_TO, msg.as_string())
        print("[notifier] Sent: " + subject)
        return True
    except Exception as exc:
        print("[notifier] Email failed: " + str(exc))
        return False


def send_health_alert(failed_steps, empty_data_items):
    """Alert when pipeline steps fail or key CSVs look empty."""
    if not failed_steps and not empty_data_items:
        return False
    lines = ["Your AltData pipeline ran into problems:\n"]
    if failed_steps:
        lines.append("FAILED STEPS:")
        for s in failed_steps:
            lines.append("  x  " + s)
        lines.append("")
    if empty_data_items:
        lines.append("EMPTY / MISSING DATA:")
        for item in empty_data_items:
            lines.append("  !  " + item)
        lines.append("")
    lines.append("Check the log:")
    lines.append("  tail -50 ~/Desktop/AltDataMktgSigns/project/data/pipeline_log.txt")
    return send_email(
        subject="AltData Pipeline Alert — {} failed, {} empty".format(
            len(failed_steps), len(empty_data_items)
        ),
        body="\n".join(lines),
    )


def send_daily_summary(top_bullish, top_bearish, run_date):
    """Morning summary: top 5 bullish and top 5 bearish tickers."""
    lines = ["AltData Morning Summary — " + run_date + "\n"]
    lines.append("TOP 5 MOST BULLISH:")
    if top_bullish:
        for ticker, score, detail in top_bullish:
            lines.append("  {:<6}  score {:+d}  {}".format(ticker, score, detail))
    else:
        lines.append("  (no bullish signals today)")
    lines.append("")
    lines.append("TOP 5 MOST BEARISH:")
    if top_bearish:
        for ticker, score, detail in top_bearish:
            lines.append("  {:<6}  score {:+d}  {}".format(ticker, score, detail))
    else:
        lines.append("  (no bearish signals today)")
    lines.append("\nDashboard: " + _DASHBOARD)
    return send_email(
        subject="AltData Daily Summary — " + run_date,
        body="\n".join(lines),
    )


def send_signal_flip_alerts(flipped, run_date):
    """Alert when tickers flip from NEUTRAL to BULLISH or BEARISH."""
    if not flipped:
        return False
    lines = ["Signal Flip Alert — " + run_date + "\n", "Tickers that changed signal:\n"]
    for ticker, prev, curr in flipped:
        arrow = "up" if curr == "BULLISH" else "dn"
        lines.append("  [{}] {:<6}  {} -> {}".format(arrow, ticker, prev, curr))
    lines.append("\nDashboard: " + _DASHBOARD)
    tickers_str = ", ".join(t for t, _, _ in flipped)
    return send_email(
        subject="AltData Signal Flip: " + tickers_str,
        body="\n".join(lines),
    )


def send_price_alerts(big_movers, run_date):
    """Alert when any stock moves more than 5% in a single day."""
    if not big_movers:
        return False
    lines = ["Price Alert — " + run_date + "\n", "Stocks with >5% single-day moves:\n"]
    for ticker, pct, price in big_movers:
        sign = "+" if pct > 0 else ""
        lines.append("  {:<6}  {}{:.1f}%  ${:.2f}".format(ticker, sign, pct, price))
    lines.append("\nDashboard: " + _DASHBOARD)
    return send_email(
        subject="AltData Price Alert: {} stock(s) moved >5%".format(len(big_movers)),
        body="\n".join(lines),
    )
