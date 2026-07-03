from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Request, Body
from fastapi.responses import JSONResponse, Response, RedirectResponse, StreamingResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import csv
import io
import re
import asyncio
import httpx
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
import uuid
import hashlib
import secrets
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import resend as resend_lib
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# ── Google / Gmail ────────────────────────────────────────────
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Web Push ──────────────────────────────────────────────────
from pywebpush import webpush, WebPushException


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

CUSTOM_DB_FILE = ROOT_DIR / '.db_override'
DB_NAME = os.environ['DB_NAME']

# ── Backup directory ──────────────────────────────────────────
BACKUP_DIR = ROOT_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

# ── Updates directory ─────────────────────────────────────────
UPDATES_DIR = ROOT_DIR / "uploads" / "updates"
UPDATES_DIR.mkdir(parents=True, exist_ok=True)

# ── Google / VAPID config ─────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI  = 'https://event-reserve-pro-5.preview.emergentagent.com/api/oauth/gmail/callback'
GMAIL_SCOPES         = ['https://www.googleapis.com/auth/gmail.send', 'openid', 'https://www.googleapis.com/auth/userinfo.email']
VAPID_PUBLIC_KEY     = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY    = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_EMAIL          = os.environ.get('VAPID_EMAIL', 'mailto:admin@cinema-productions.com')

# In-memory dedup: avoid sending the same reminder twice in one day
_sent_push_today: set = set()

# Active MongoDB URL: prefer custom override file
_mongo_url = CUSTOM_DB_FILE.read_text().strip() if CUSTOM_DB_FILE.exists() else os.environ['MONGO_URL']
client = AsyncIOMotorClient(_mongo_url)
db = client[DB_NAME]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ─── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    scheduler.add_job(
        check_and_send_reminders,
        CronTrigger(hour=8, minute=0),
        id="daily_reminders",
        replace_existing=True
    )
    # Per-minute push + Gmail reminders
    scheduler.add_job(
        check_and_push_reminders,
        IntervalTrigger(minutes=1),
        id="push_reminders",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started")
    yield
    scheduler.shutdown()
    client.close()
    logger.info("Scheduler stopped")


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")


# ─── Helper ──────────────────────────────────────────────
def doc_to_dict(doc: dict) -> dict:
    if doc is None:
        return {}
    d = {k: v for k, v in doc.items() if k != '_id'}
    if '_id' in doc:
        d['id'] = str(doc['_id'])
    return d


# ─── Pydantic Models ─────────────────────────────────────
class ReservationCreate(BaseModel):
    client_name: str
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    event_type: str
    event_date: str
    event_time: Optional[str] = None
    venue: Optional[str] = None
    guests_count: Optional[int] = None
    total_amount: float
    advance_paid: float = 0.0
    status: str = "Pendiente"
    notes: Optional[str] = None
    package_type: Optional[str] = None


class ReservationUpdate(BaseModel):
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    venue: Optional[str] = None
    guests_count: Optional[int] = None
    total_amount: Optional[float] = None
    advance_paid: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    locations: Optional[list] = None
    assigned_partners: Optional[list] = None
    package_type: Optional[str] = None


class SocioCreate(BaseModel):
    name: str
    role: str = "Fotógrafo"
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    rate_per_event: Optional[float] = None


class SocioUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    rate_per_event: Optional[float] = None


class NotificationSettingsModel(BaseModel):
    reminders_enabled: bool = False
    reminder_periods: List[int] = [3]        # days before: [7, 3, 1, 0]
    reminder_time: Optional[str] = "09:00"   # daily send time HH:MM
    reminder_hours_before: int = 0           # 0 = disabled; N = send N hrs before event
    admin_email: Optional[str] = None
    admin_whatsapp: Optional[str] = None
    notification_channel: str = "email"
    resend_api_key: Optional[str] = None
    # ── New email fields ───────────────────────────────────────
    sender_name: Optional[str] = "Cinema Productions"
    cc_emails: Optional[str] = None          # comma-separated CC emails
    email_subject: Optional[str] = None      # custom subject template
    notify_client: bool = False              # also email client_email field
    telegram_enabled: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    ntfy_enabled: bool = False
    ntfy_topic: Optional[str] = None
    # ── Business config ────────────────────────────────────────
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_website: Optional[str] = None
    company_tax_id: Optional[str] = None
    timezone: Optional[str] = "America/Guatemala"
    default_advance_pct: Optional[int] = 30
    business_hours_start: Optional[str] = "08:00"
    business_hours_end: Optional[str] = "22:00"
    backup_retention: Optional[int] = 10
    auto_cleanup_months: Optional[int] = None  # None = disabled


class DBConnectRequest(BaseModel):
    url: str


# ─── Reminder Logic ──────────────────────────────────────
def _build_reminder_html(events: list, days: int, sender_name: str = "Cinema Productions") -> str:
    rows = ""
    for ev in events:
        balance = ev.get("total_amount", 0) - ev.get("advance_paid", 0)
        balance_str = f"Q{balance:,.2f}" if balance > 0 else '<span style="color:#10b981;font-weight:bold;">Pagado</span>'
        rows += f"""
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">{ev.get('client_name','')}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">{ev.get('event_type','')}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">{ev.get('event_date','')} {ev.get('event_time','')}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">{ev.get('venue') or '—'}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #e5e7eb;">{balance_str}</td>
        </tr>"""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8fafc;padding:32px;">
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px 16px 0 0;padding:24px 32px;">
        <h1 style="color:#fff;margin:0;font-size:22px;">{sender_name}</h1>
        <p style="color:rgba(255,255,255,0.85);margin:4px 0 0;font-size:14px;">Recordatorio de eventos próximos</p>
      </div>
      <div style="background:#fff;border-radius:0 0 16px 16px;padding:24px 32px;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
        <p style="color:#374151;font-size:16px;margin-top:0;">
          Tienes <strong>{len(events)} evento(s)</strong> programado(s) en <strong>{days} día(s)</strong>:
        </p>
        <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:13px;">
          <thead>
            <tr style="background:#f1f5f9;">
              <th style="padding:10px 16px;text-align:left;color:#6366f1;">Cliente</th>
              <th style="padding:10px 16px;text-align:left;color:#6366f1;">Tipo</th>
              <th style="padding:10px 16px;text-align:left;color:#6366f1;">Fecha / Hora</th>
              <th style="padding:10px 16px;text-align:left;color:#6366f1;">Lugar</th>
              <th style="padding:10px 16px;text-align:left;color:#6366f1;">Saldo</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="color:#9ca3af;font-size:11px;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:16px;">
          {sender_name} — Sistema de Gestión de Reservas · Este es un recordatorio automático
        </p>
      </div>
    </div>"""


def _build_client_reminder_html(ev: dict, days: int, sender_name: str = "Cinema Productions") -> str:
    balance = ev.get("total_amount", 0) - ev.get("advance_paid", 0)
    balance_str = f"Saldo pendiente: Q{balance:,.2f}" if balance > 0 else "Pago completado ✓"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;background:#f8fafc;padding:32px;">
      <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px 16px 0 0;padding:24px 32px;">
        <h1 style="color:#fff;margin:0;font-size:20px;">{sender_name}</h1>
        <p style="color:rgba(255,255,255,0.85);margin:4px 0 0;font-size:14px;">Recordatorio de tu evento</p>
      </div>
      <div style="background:#fff;border-radius:0 0 16px 16px;padding:24px 32px;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
        <p style="color:#374151;font-size:16px;margin-top:0;">Hola <strong>{ev.get('client_name','')}</strong>,</p>
        <p style="color:#374151;">Te recordamos que tu evento está programado en <strong>{days} día(s)</strong>:</p>
        <div style="background:#f1f5f9;border-radius:12px;padding:20px;margin:16px 0;">
          <p style="margin:0 0 8px;color:#6366f1;font-weight:bold;">{ev.get('event_type', 'Evento')}</p>
          <p style="margin:0 0 6px;color:#374151;">📅 {ev.get('event_date', '')} {ev.get('event_time', '')}</p>
          <p style="margin:0 0 6px;color:#374151;">📍 {ev.get('venue') or 'Por confirmar'}</p>
          <p style="margin:0;color:#374151;">💳 {balance_str}</p>
        </div>
        <p style="color:#9ca3af;font-size:11px;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:16px;">
          {sender_name} — Este es un recordatorio automático
        </p>
      </div>
    </div>"""


async def check_and_send_reminders():
    """Daily cron job: send reminders for upcoming events."""
    try:
        settings_doc = await db.app_settings.find_one({}, {"_id": 0})
        if not settings_doc or not settings_doc.get("reminders_enabled"):
            return

        days = int(settings_doc.get("reminder_days", 3))
        target_date = (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()

        cursor = db.reservations.find(
            {"event_date": target_date, "status": {"$nin": ["Cancelado", "Completado"]}},
            {"client_name": 1, "event_date": 1, "event_time": 1, "event_type": 1, "venue": 1, "total_amount": 1, "advance_paid": 1, "email": 1, "_id": 0}
        )
        upcoming = await cursor.to_list(100)

        if not upcoming:
            logger.info(f"No events on {target_date}, skipping reminders.")
            return

        channel = settings_doc.get("notification_channel", "email")
        sender_name = settings_doc.get("sender_name") or "Cinema Productions"
        custom_subject = settings_doc.get("email_subject") or f"Recordatorio: {len(upcoming)} evento(s) en {days} día(s)"
        cc_raw = settings_doc.get("cc_emails") or ""
        cc_list = [e.strip() for e in cc_raw.split(",") if e.strip()]
        notify_client = settings_doc.get("notify_client", False)
        logger.info(f"Sending reminders for {len(upcoming)} events on {target_date} via {channel}")

        if channel in ("email", "both"):
            api_key = settings_doc.get("resend_api_key")
            admin_email = settings_doc.get("admin_email")
            if api_key and admin_email:
                resend_lib.api_key = api_key
                html = _build_reminder_html(upcoming, days, sender_name)
                to_list = [admin_email] + cc_list
                params = {
                    "from": f"{sender_name} <onboarding@resend.dev>",
                    "to": to_list,
                    "subject": custom_subject,
                    "html": html,
                }
                await asyncio.to_thread(resend_lib.Emails.send, params)
                logger.info(f"Reminder email sent to {to_list}")
                # Also notify each client if they have email
                if notify_client:
                    for ev in upcoming:
                        client_email = ev.get("email")
                        if client_email:
                            client_params = {
                                "from": f"{sender_name} <onboarding@resend.dev>",
                                "to": [client_email],
                                "subject": f"Recordatorio de tu evento — {ev.get('event_type', '')} el {ev.get('event_date', '')}",
                                "html": _build_client_reminder_html(ev, days, sender_name),
                            }
                            await asyncio.to_thread(resend_lib.Emails.send, client_params)
            else:
                logger.warning("Email reminders enabled but api_key or admin_email missing.")

    except Exception as e:
        logger.error(f"Error in reminder job: {e}")


# ─── Gmail Helper ─────────────────────────────────────────────
async def _get_gmail_service():
    """Return authenticated Gmail API service using stored refresh token."""
    token_doc = await db.oauth_tokens.find_one({"provider": "gmail"}, {"_id": 0})
    if not token_doc or not token_doc.get("refresh_token"):
        raise Exception("Gmail not connected. Connect via Settings → Notificaciones.")
    creds = Credentials(
        token=token_doc.get("access_token"),
        refresh_token=token_doc["refresh_token"],
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=GMAIL_SCOPES,
    )
    if not creds.valid:
        await asyncio.to_thread(creds.refresh, GoogleRequest())
        await db.oauth_tokens.update_one(
            {"provider": "gmail"},
            {"$set": {"access_token": creds.token}},
        )
    return build("gmail", "v1", credentials=creds), token_doc.get("email", "me")


async def _send_gmail(to: str, subject: str, html: str):
    service, from_email = await _get_gmail_service()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    await asyncio.to_thread(
        service.users().messages().send(userId="me", body={"raw": raw}).execute
    )
    logger.info(f"Gmail sent to {to}: {subject}")


# ─── Web Push Helper ──────────────────────────────────────────
async def _send_push_to_all(title: str, body: str, url: str = "/dashboard"):
    subscriptions = await db.push_subscriptions.find({}).to_list(1000)
    if not subscriptions:
        return
    expired = []
    for sub in subscriptions:
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_EMAIL},
            )
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                expired.append(sub["endpoint"])
            logger.error(f"Push send error: {e}")
    for ep in expired:
        await db.push_subscriptions.delete_one({"endpoint": ep})
    logger.info(f"Push sent to {len(subscriptions) - len(expired)} subscribers")


# ─── Telegram Helper ──────────────────────────────────────────
async def _send_telegram(bot_token: str, chat_id: str, text: str):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
        r.raise_for_status()


def _build_telegram_text(events: list, days: int) -> str:
    lines = ["<b>Cinema Productions</b> — Recordatorio\n"]
    lines.append(f"Tienes <b>{len(events)} evento(s)</b> en <b>{days} día(s)</b>:\n")
    for ev in events:
        date = ev.get("event_date", "")
        time_str = ev.get("event_time", "")
        when = f"{date} {time_str}".strip()
        lines.append(
            f"• <b>{ev.get('client_name','?')}</b> — {ev.get('event_type','?')}\n"
            f"  {when} — {ev.get('venue') or 'Sin lugar'}"
        )
    return "\n".join(lines)


# ─── ntfy.sh Helper ───────────────────────────────────────────
async def _send_ntfy(topic: str, title: str, message: str, priority: str = "default"):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"https://ntfy.sh/{topic}",
            content=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "calendar,bell",
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
        r.raise_for_status()


# ─── Per-minute reminder check (all channels) ────────────────
async def _dispatch_reminders(events: list, days_label: str, settings: dict):
    """Send a reminder for `events` via every enabled channel."""
    if not events:
        return

    title = f"Recordatorio: {len(events)} evento(s) en {days_label}"
    body  = ", ".join(r.get("client_name", "?") for r in events[:3])
    if len(events) > 3:
        body += f" y {len(events) - 3} más"

    # ── Email (Resend) ──────────────────────────
    channel = settings.get("notification_channel", "email")
    if channel in ("email", "both"):
        api_key     = settings.get("resend_api_key")
        admin_email = settings.get("admin_email")
        if api_key and admin_email:
            try:
                resend_lib.api_key = api_key
                html = _build_reminder_html(events, int(days_label.split()[0]) if days_label[0].isdigit() else 0)
                params = {
                    "from": "Cinema Productions <onboarding@resend.dev>",
                    "to": [admin_email],
                    "subject": title,
                    "html": html,
                }
                await asyncio.to_thread(resend_lib.Emails.send, params)
                logger.info(f"[Reminders] Email sent to {admin_email}")
            except Exception as e:
                logger.warning(f"[Reminders] Email failed: {e}")

    # ── Telegram ────────────────────────────────
    if settings.get("telegram_enabled") and settings.get("telegram_bot_token") and settings.get("telegram_chat_id"):
        try:
            text = _build_telegram_text(events, int(days_label.split()[0]) if days_label[0].isdigit() else 0)
            await _send_telegram(settings["telegram_bot_token"], settings["telegram_chat_id"], text)
            logger.info("[Reminders] Telegram sent")
        except Exception as e:
            logger.warning(f"[Reminders] Telegram failed: {e}")

    # ── ntfy.sh ─────────────────────────────────
    if settings.get("ntfy_enabled") and settings.get("ntfy_topic"):
        try:
            await _send_ntfy(settings["ntfy_topic"], title, body, priority="high")
            logger.info("[Reminders] ntfy sent")
        except Exception as e:
            logger.warning(f"[Reminders] ntfy failed: {e}")

    # ── Browser Push ────────────────────────────
    await _send_push_to_all(title, body, "/dashboard")


async def check_and_push_reminders():
    """Per-minute job: fires reminders for each configured period and hours-before."""
    global _sent_push_today
    try:
        settings_doc = await db.app_settings.find_one({}, {"_id": 0})
        if not settings_doc or not settings_doc.get("reminders_enabled"):
            return

        reminder_time   = settings_doc.get("reminder_time", "09:00")
        reminder_periods = settings_doc.get("reminder_periods") or [settings_doc.get("reminder_days", 3)]
        hours_before    = int(settings_doc.get("reminder_hours_before", 0))
        now             = datetime.now(timezone.utc)
        current_hhmm    = now.strftime("%H:%M")
        today_str       = now.strftime("%Y-%m-%d")

        # ── Days-based reminders ───────────────────────────────
        if current_hhmm == reminder_time:
            for days in reminder_periods:
                target_date = (now.date() + timedelta(days=days)).isoformat()
                dedup_key   = f"days_{today_str}_{days}"
                if dedup_key in _sent_push_today:
                    continue
                _sent_push_today.add(dedup_key)

                cursor = db.reservations.find(
                    {"event_date": target_date, "status": {"$nin": ["Cancelado", "Completado"]}},
                    {"client_name": 1, "event_date": 1, "event_time": 1, "event_type": 1, "venue": 1, "_id": 0}
                )
                upcoming = await cursor.to_list(100)
                label = f"{days} día(s)" if days > 0 else "hoy"
                await _dispatch_reminders(upcoming, label, settings_doc)

        # ── Hours-before reminders (same day events) ───────────
        if hours_before > 0:
            cursor = db.reservations.find(
                {"event_date": today_str, "status": {"$nin": ["Cancelado", "Completado"]}},
                {"client_name": 1, "event_date": 1, "event_time": 1, "event_type": 1, "venue": 1, "_id": 0}
            )
            today_events = await cursor.to_list(100)
            for ev in today_events:
                et = ev.get("event_time")
                if not et:
                    continue
                try:
                    event_dt = datetime.strptime(f"{today_str} {et}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                    reminder_dt = event_dt - timedelta(hours=hours_before)
                    reminder_hhmm = reminder_dt.strftime("%H:%M")
                    if current_hhmm != reminder_hhmm:
                        continue
                    dedup_key = f"hours_{today_str}_{ev.get('client_name','')}_{et}"
                    if dedup_key in _sent_push_today:
                        continue
                    _sent_push_today.add(dedup_key)
                    await _dispatch_reminders([ev], f"{hours_before}h antes", settings_doc)
                except Exception:
                    continue

        # Clear dedup set daily
        if len(_sent_push_today) > 1000:
            _sent_push_today.clear()

    except Exception as e:
        logger.error(f"Error in reminder job: {e}")


# ─── Routes ──────────────────────────────────────────────

@api_router.get("/")
async def root():
    return {"message": "Event Reservation API"}


@api_router.get("/deployment/env-template")
async def get_env_template():
    """Returns a .env template for deployment (with current non-sensitive values where safe)."""
    settings = await db.app_settings.find_one({}, {"_id": 0}) or {}
    template = f"""# ══════════════════════════════════════════
# Cinema Productions — Deployment Config
# ══════════════════════════════════════════
# Copy this file to .env and fill in the values

# ── Database ──────────────────────────────
MONGO_URL=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
DB_NAME=cinema_productions

# ── App URLs ──────────────────────────────
REACT_APP_BACKEND_URL=https://your-domain.com

# ── Email (Resend) ─────────────────────────
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx

# ── Notifications ─────────────────────────
# Telegram (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ntfy.sh (optional, free)
NTFY_TOPIC={settings.get('ntfy_topic', 'cinema-reservas')}

# ── Web Push (optional) ───────────────────
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@yourdomain.com

# ══════════════════════════════════════════
# Docker Compose: docker-compose up -d
# Railway: connect GitHub repo and add these vars
# Render: add as Environment Variables in dashboard
# ══════════════════════════════════════════
"""
    return Response(
        content=template.encode(),
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename=".env.template"'},
    )


@api_router.get("/deployment/docker-compose")
async def get_docker_compose():
    """Returns a docker-compose.yml for self-hosting."""
    compose = """version: '3.9'
services:
  backend:
    image: python:3.11-slim
    working_dir: /app/backend
    command: uvicorn server:app --host 0.0.0.0 --port 8001 --reload
    volumes:
      - ./backend:/app/backend
    env_file: .env
    ports:
      - "8001:8001"
    restart: unless-stopped
    depends_on:
      - mongo

  frontend:
    image: node:20-alpine
    working_dir: /app/frontend
    command: sh -c "yarn install && yarn build && npx serve -s build -l 3000"
    volumes:
      - ./frontend:/app/frontend
    env_file: .env
    ports:
      - "3000:3000"
    restart: unless-stopped

  mongo:
    image: mongo:7
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"
    restart: unless-stopped
    # Note: Use MongoDB Atlas instead of local mongo for production

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  mongo_data:

# ─── Usage ────────────────────────────────
# 1. Copy .env.template to .env and fill values
# 2. docker-compose up -d
# 3. Access: http://your-server-ip
"""
    return Response(
        content=compose.encode(),
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="docker-compose.yml"'},
    )


@api_router.post("/deployment/health-check")
async def health_check_url(url: str):
    """Pings a URL and returns if it's responding."""
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "URL inválida"}
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            r = await client.get(url)
            return {
                "ok": r.status_code < 400,
                "status": r.status_code,
                "latency_ms": round(r.elapsed.total_seconds() * 1000),
                "message": f"HTTP {r.status_code} — responde en {round(r.elapsed.total_seconds()*1000)}ms",
            }
    except httpx.TimeoutException:
        return {"ok": False, "error": "Timeout — no responde (>8s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}



@api_router.delete("/data/clear-all")
async def clear_all_data_endpoint(auto_backup: bool = True):
    """Elimina todas las reservas y socios. Crea respaldo automático si auto_backup=True."""
    return await clear_all_data(auto_backup=auto_backup)


async def clear_all_data(auto_backup: bool = True):
    """Elimina todas las reservas y socios. Crea respaldo automático si auto_backup=True."""
    if auto_backup:
        try:
            await _create_backup(label="auto_pre_delete")
        except Exception as e:
            logger.warning(f"Auto-backup before clear failed: {e}")
    res_result  = await db.reservations.delete_many({})
    soc_result  = await db.socios.delete_many({})
    return {
        "ok": True,
        "deleted_reservations": res_result.deleted_count,
        "deleted_socios": soc_result.deleted_count,
        "auto_backup_created": auto_backup,
    }


@api_router.post("/data/cleanup")
async def cleanup_data(action: str = "cancelled", months_old: int = 6):
    """
    Limpieza selectiva de datos.
    action: 'cancelled' | 'old_completed' | 'preview'
    """
    await _create_backup(label="auto_pre_cleanup")

    if action == "cancelled":
        result = await db.reservations.delete_many({"status": "Cancelado"})
        return {"ok": True, "deleted": result.deleted_count, "message": f"{result.deleted_count} reservas canceladas eliminadas"}

    elif action == "old_completed":
        cutoff = datetime.now(timezone.utc) - timedelta(days=months_old * 30)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        # Find completed reservations older than cutoff
        cursor = db.reservations.find({"status": "Completado"})
        docs = await cursor.to_list(100000)
        ids_to_delete = []
        for d in docs:
            date_str = d.get("event_date", "")
            if date_str and date_str < cutoff_str:
                ids_to_delete.append(d["_id"])
        if ids_to_delete:
            result = await db.reservations.delete_many({"_id": {"$in": ids_to_delete}})
            return {"ok": True, "deleted": result.deleted_count, "message": f"{result.deleted_count} reservas completadas antiguas eliminadas"}
        return {"ok": True, "deleted": 0, "message": "No hay reservas completadas antiguas para eliminar"}

    elif action == "preview":
        # Return counts without deleting
        cancelled_count = await db.reservations.count_documents({"status": "Cancelado"})
        cutoff = datetime.now(timezone.utc) - timedelta(days=months_old * 30)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        cursor = db.reservations.find({"status": "Completado"})
        docs = await cursor.to_list(100000)
        old_completed = sum(1 for d in docs if d.get("event_date", "") < cutoff_str)
        return {
            "ok": True,
            "cancelled_count": cancelled_count,
            "old_completed_count": old_completed,
            "months_threshold": months_old,
        }

    return {"ok": False, "message": "Acción no reconocida"}


@api_router.post("/import/reservations")
async def import_reservations_csv(file: UploadFile = File(...)):
    """Import reservations from a CSV file. Returns count of imported records."""
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    # Column mapping: accept various header names
    FIELD_MAP = {
        "client_name":  ["client_name", "nombre", "cliente", "name"],
        "client_phone": ["client_phone", "telefono", "teléfono", "phone"],
        "client_email": ["client_email", "email", "correo"],
        "event_type":   ["event_type", "tipo_evento", "tipo", "type"],
        "event_date":   ["event_date", "fecha", "date", "fecha_evento"],
        "event_time":   ["event_time", "hora", "time"],
        "venue":        ["venue", "lugar", "location", "ubicacion"],
        "guests_count": ["guests_count", "invitados", "guests"],
        "total_amount": ["total_amount", "total", "monto_total"],
        "advance_paid": ["advance_paid", "anticipo", "advance", "pago_anticipado"],
        "status":       ["status", "estado"],
        "notes":        ["notes", "notas", "note"],
    }

    def find_col(headers, candidates):
        headers_lower = {h.lower().strip(): h for h in headers}
        for c in candidates:
            if c.lower() in headers_lower:
                return headers_lower[c.lower()]
        return None

    imported = 0
    errors   = []
    now_str  = datetime.now(timezone.utc).isoformat()

    for i, row in enumerate(reader, start=2):
        try:
            headers = list(row.keys())
            def get(field):
                col = find_col(headers, FIELD_MAP.get(field, [field]))
                return row.get(col, "").strip() if col else ""

            client_name = get("client_name")
            if not client_name:
                errors.append(f"Fila {i}: nombre vacío — omitida")
                continue

            event_date = get("event_date") or ""
            total_raw  = get("total_amount") or "0"
            advance_raw = get("advance_paid") or "0"

            # Sanitize numbers
            def to_float(s):
                s = re.sub(r"[^\d.]", "", s)
                return float(s) if s else 0.0

            doc = {
                "client_name":   client_name,
                "client_phone":  get("client_phone") or None,
                "client_email":  get("client_email") or None,
                "event_type":    get("event_type") or "Otro",
                "event_date":    event_date,
                "event_time":    get("event_time") or None,
                "venue":         get("venue") or None,
                "guests_count":  int(get("guests_count")) if get("guests_count").isdigit() else None,
                "total_amount":  to_float(total_raw),
                "advance_paid":  to_float(advance_raw),
                "status":        get("status") or "Pendiente",
                "notes":         get("notes") or None,
                "receipts":      [],
                "locations":     [],
                "assigned_partners": [],
                "created_at":    now_str,
                "imported_from_csv": True,
            }
            await db.reservations.insert_one(doc)
            imported += 1
        except Exception as e:
            errors.append(f"Fila {i}: {str(e)}")

    return {
        "ok": True,
        "imported": imported,
        "errors": errors[:10],  # limit error list
        "message": f"{imported} reservas importadas correctamente" + (f" ({len(errors)} errores)" if errors else ""),
    }


@api_router.get("/export/reservations/xlsx")
async def export_reservations_xlsx():
    """Export reservations as Excel (.xlsx) file."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        import io as _io

        cursor = db.reservations.find({}, {"_id": 0, "receipts": 0, "assigned_partners": 0, "locations": 0})
        docs   = await cursor.to_list(100000)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reservas"

        headers = ["Nombre", "Teléfono", "Email", "Tipo Evento", "Fecha", "Hora",
                   "Lugar", "Invitados", "Total", "Anticipo", "Saldo", "Estado", "Notas", "Creado"]
        keys    = ["client_name", "client_phone", "client_email", "event_type", "event_date",
                   "event_time", "venue", "guests_count", "total_amount", "advance_paid",
                   None, "status", "notes", "created_at"]

        # Header row
        header_fill = PatternFill("solid", fgColor="4F46E5")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        alt_fill = PatternFill("solid", fgColor="F8F7FF")
        for row_idx, doc in enumerate(docs, start=2):
            fill = alt_fill if row_idx % 2 == 0 else None
            for col_idx, key in enumerate(keys, start=1):
                if key is None:
                    # Saldo = total - anticipo
                    total   = doc.get("total_amount") or 0
                    advance = doc.get("advance_paid") or 0
                    value   = total - advance
                else:
                    value = doc.get(key, "")
                    if isinstance(value, float) and value == int(value):
                        value = int(value)
                cell = ws.cell(row=row_idx + 1 - 1, column=col_idx, value=value)
                if fill:
                    cell.fill = fill

        # Auto-width
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=8)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 40)

        buf = _io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="reservaciones_{ts}.xlsx"'},
        )
    except ImportError:
        return JSONResponse({"error": "openpyxl no instalado"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Backup helpers ───────────────────────────────────────────
BACKUP_COLLECTIONS = ["reservations", "socios", "app_settings"]

async def _create_backup(label: str = "manual") -> dict:
    """Create a JSON backup of all main collections, store in BACKUP_DIR."""
    backup_data: dict = {"_meta": {"created_at": datetime.now(timezone.utc).isoformat(), "label": label}}
    for cname in BACKUP_COLLECTIONS:
        cursor = db[cname].find({})
        docs = await cursor.to_list(100000)
        backup_data[cname] = [doc_to_dict(d) for d in docs]

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{label}_{ts}.json"
    filepath = BACKUP_DIR / filename
    filepath.write_text(json.dumps(backup_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Keep only the last 15 backups (oldest removed first)
    existing = sorted(BACKUP_DIR.glob("backup_*.json"), key=lambda f: f.stat().st_mtime)
    for old in existing[:-15]:
        old.unlink(missing_ok=True)

    total_docs = sum(len(v) for k, v in backup_data.items() if k != "_meta")
    return {"filename": filename, "docs": total_docs}


# ─── Backup endpoints ─────────────────────────────────────────

@api_router.get("/backup/download")
async def download_full_backup():
    """Download a complete backup of all collections as JSON (for local PC)."""
    backup_data: dict = {"_meta": {"created_at": datetime.now(timezone.utc).isoformat(), "app": "Cinema Productions"}}
    for cname in BACKUP_COLLECTIONS:
        cursor = db[cname].find({})
        docs = await cursor.to_list(100000)
        backup_data[cname] = [doc_to_dict(d) for d in docs]

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"cinema_backup_{ts}.json"
    content = json.dumps(backup_data, ensure_ascii=False, indent=2)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.post("/backup/create")
async def create_server_backup():
    """Create and save a backup on the server (history list)."""
    try:
        result = await _create_backup(label="manual")
        return {"success": True, **result, "message": f"Respaldo creado: {result['docs']} documentos"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear respaldo: {e}")


@api_router.get("/backup/history")
async def list_backups():
    """List all server-side backups (newest first)."""
    files = sorted(BACKUP_DIR.glob("backup_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        stat = f.stat()
        size_kb = stat.st_size / 1024
        size_str = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        label = "auto" if "auto_" in f.name else "manual"
        result.append({
            "filename": f.name,
            "size": size_str,
            "label": label,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return result


@api_router.get("/backup/{filename}/download")
async def download_backup_file(filename: str):
    """Download a specific server-side backup by filename."""
    # Security: only allow .json files in BACKUP_DIR
    if not filename.endswith(".json") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    filepath = BACKUP_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Respaldo no encontrado")
    return Response(
        content=filepath.read_bytes(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.delete("/backup/{filename}")
async def delete_backup_file(filename: str):
    """Delete a specific server-side backup."""
    if not filename.endswith(".json") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    filepath = BACKUP_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Respaldo no encontrado")
    filepath.unlink()
    return {"success": True, "message": "Respaldo eliminado"}


@api_router.post("/backup/restore")
async def restore_backup(file: UploadFile = File(...)):
    """Restore all collections from an uploaded JSON backup file."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="El archivo debe ser .json")
    try:
        content = await file.read()
        backup_data = json.loads(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Archivo JSON inválido o corrupto")

    # Auto-save current state before restore
    try:
        await _create_backup(label="auto_pre_restore")
    except Exception as e:
        logger.warning(f"Pre-restore backup failed: {e}")

    restored: dict = {}
    errors: list = []
    for cname in BACKUP_COLLECTIONS:
        docs = backup_data.get(cname)
        if docs is None or not isinstance(docs, list):
            continue
        try:
            # Remove serialized ids so MongoDB assigns fresh _id
            clean_docs = []
            for d in docs:
                d.pop("id", None)
                d.pop("_id", None)
                clean_docs.append(d)
            await db[cname].delete_many({})
            if clean_docs:
                await db[cname].insert_many(clean_docs)
            restored[cname] = len(clean_docs)
        except Exception as e:
            errors.append(f"{cname}: {e}")

    if errors:
        raise HTTPException(status_code=500, detail="Errores al restaurar: " + " | ".join(errors))

    total = sum(restored.values())
    return {"success": True, "restored": restored, "total": total,
            "message": f"Restaurado correctamente: {total} documentos en {len(restored)} colecciones"}


@api_router.get("/stats")
async def get_stats():
    total = await db.reservations.count_documents({})
    upcoming = await db.reservations.count_documents({
        "event_date": {"$gte": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        "status": {"$nin": ["Cancelado", "Completado"]}
    })
    active_cursor = db.reservations.find(
        {"status": {"$nin": ["Cancelado"]}},
        {"total_amount": 1, "advance_paid": 1, "assigned_partners": 1, "_id": 0}
    )
    active_docs = await active_cursor.to_list(1000)
    total_pending = sum(
        max(0, (d.get("total_amount", 0) or 0) - (d.get("advance_paid", 0) or 0))
        for d in active_docs
    )
    total_event_amount = sum((d.get("total_amount", 0) or 0) for d in active_docs)
    total_partner_cost = sum(
        p.get("payment", 0) or 0
        for d in active_docs
        for p in (d.get("assigned_partners") or [])
    )
    return {
        "total_reservations": total,
        "upcoming_events": upcoming,
        "pending_payment": round(total_pending, 2),
        "real_income": round(total_event_amount - total_partner_cost, 2),
    }


@api_router.get("/reservations")
async def list_reservations():
    cursor = db.reservations.find({}, {"receipt_images.data": 0})
    docs = await cursor.to_list(1000)
    return [doc_to_dict(d) for d in docs]


@api_router.post("/reservations", status_code=201)
async def create_reservation(reservation: ReservationCreate):
    doc = reservation.model_dump()
    doc["receipt_images"] = []
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.reservations.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@api_router.get("/reservations/{reservation_id}")
async def get_reservation(reservation_id: str):
    try:
        oid = ObjectId(reservation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await db.reservations.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return doc_to_dict(doc)


@api_router.put("/reservations/{reservation_id}")
async def update_reservation(reservation_id: str, reservation: ReservationUpdate):
    try:
        oid = ObjectId(reservation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    update_data = {k: v for k, v in reservation.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    result = await db.reservations.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    doc = await db.reservations.find_one({"_id": oid})
    return doc_to_dict(doc)


@api_router.delete("/reservations/{reservation_id}")
async def delete_reservation(reservation_id: str):
    try:
        oid = ObjectId(reservation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await db.reservations.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return {"message": "Reserva eliminada"}


@api_router.post("/reservations/{reservation_id}/receipts")
async def upload_receipt(reservation_id: str, file: UploadFile = File(...)):
    try:
        oid = ObjectId(reservation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo muy grande (máx 10MB)")
    b64 = base64.b64encode(content).decode("utf-8")
    receipt = {
        "id": str(uuid.uuid4()),
        "filename": file.filename,
        "content_type": file.content_type,
        "data": b64,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.reservations.update_one(
        {"_id": oid}, {"$push": {"receipt_images": receipt}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return {k: v for k, v in receipt.items() if k != "data"}


@api_router.delete("/reservations/{reservation_id}/receipts/{receipt_id}")
async def delete_receipt(reservation_id: str, receipt_id: str):
    try:
        oid = ObjectId(reservation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await db.reservations.update_one(
        {"_id": oid}, {"$pull": {"receipt_images": {"id": receipt_id}}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return {"message": "Comprobante eliminado"}


@api_router.get("/export/reservations")
async def export_reservations(format: str = "csv"):
    cursor = db.reservations.find({}, {"receipt_images": 0})
    docs = await cursor.to_list(10000)
    data = [doc_to_dict(d) for d in docs]

    if format == "json":
        return JSONResponse(
            content=data,
            headers={"Content-Disposition": "attachment; filename=reservaciones.json"}
        )

    if not data:
        return Response("", media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=reservaciones.csv"})

    output = io.StringIO()
    fields = ["id", "client_name", "client_phone", "client_email", "event_type", "event_date",
              "event_time", "venue", "guests_count", "total_amount", "advance_paid", "status", "notes", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=reservaciones.csv"})


@api_router.get("/calendar")
async def get_calendar_events():
    cursor = db.reservations.find(
        {"status": {"$nin": ["Cancelado"]}},
        {"client_name": 1, "event_date": 1, "event_type": 1, "status": 1, "_id": 1}
    )
    docs = await cursor.to_list(1000)
    return [doc_to_dict(d) for d in docs]


# ─── Socios ──────────────────────────────────────────────

@api_router.get("/socios")
async def list_socios():
    cursor = db.socios.find({}, {"photo": 0, "photo_content_type": 0})
    docs = await cursor.to_list(1000)
    return [doc_to_dict(d) for d in docs]


@api_router.post("/socios", status_code=201)
async def create_socio(socio: SocioCreate):
    doc = socio.model_dump()
    doc["photo"] = None
    doc["photo_content_type"] = None
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.socios.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@api_router.get("/socios/{socio_id}")
async def get_socio(socio_id: str):
    try:
        oid = ObjectId(socio_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await db.socios.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    return doc_to_dict(doc)


@api_router.put("/socios/{socio_id}")
async def update_socio(socio_id: str, socio: SocioUpdate):
    try:
        oid = ObjectId(socio_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    update_data = {k: v for k, v in socio.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    result = await db.socios.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    doc = await db.socios.find_one({"_id": oid})
    return doc_to_dict(doc)


@api_router.delete("/socios/{socio_id}")
async def delete_socio(socio_id: str):
    try:
        oid = ObjectId(socio_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await db.socios.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    return {"message": "Socio eliminado"}


@api_router.post("/socios/{socio_id}/photo")
async def upload_socio_photo(socio_id: str, file: UploadFile = File(...)):
    try:
        oid = ObjectId(socio_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo muy grande (máx 5MB)")
    b64 = base64.b64encode(content).decode("utf-8")
    result = await db.socios.update_one(
        {"_id": oid}, {"$set": {"photo": b64, "photo_content_type": file.content_type}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Socio no encontrado")
    return {"message": "Foto actualizada"}


@api_router.delete("/socios/{socio_id}/photo")
async def delete_socio_photo(socio_id: str):
    try:
        oid = ObjectId(socio_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    await db.socios.update_one({"_id": oid}, {"$set": {"photo": None, "photo_content_type": None}})
    return {"message": "Foto eliminada"}


@api_router.get("/financials")
async def get_financials():
    cursor = db.reservations.find(
        {"status": {"$nin": ["Cancelado"]}},
        {"total_amount": 1, "advance_paid": 1, "assigned_partners": 1}
    )
    docs = await cursor.to_list(10000)
    total_event_amount = sum((d.get("total_amount") or 0) for d in docs)
    total_advance = sum((d.get("advance_paid") or 0) for d in docs)
    total_partner_cost = 0
    total_paid_to_partners = 0
    total_pending_to_partners = 0
    for d in docs:
        for p in (d.get("assigned_partners") or []):
            amt = p.get("payment") or 0
            total_partner_cost += amt
            if p.get("payment_status") == "Pagado":
                total_paid_to_partners += amt
            else:
                total_pending_to_partners += amt
    return {
        "total_event_amount": round(total_event_amount, 2),
        "total_advance": round(total_advance, 2),
        "total_partner_cost": round(total_partner_cost, 2),
        "total_paid_to_partners": round(total_paid_to_partners, 2),
        "total_pending_to_partners": round(total_pending_to_partners, 2),
        "real_income": round(total_event_amount - total_partner_cost, 2),
    }


# ─── App Settings ─────────────────────────────────────────

@api_router.get("/settings")
async def get_app_settings():
    doc = await db.app_settings.find_one({}, {"_id": 0})
    if not doc:
        return {}
    doc.pop("app_password_hash", None)
    # Mask Resend key
    if doc.get("resend_api_key"):
        key = doc["resend_api_key"]
        doc["resend_api_key"] = "re_" + "•" * 20 + key[-4:] if len(key) > 4 else "****"
        doc["has_resend_key"] = True
    else:
        doc["has_resend_key"] = False
    # Mask Telegram token
    if doc.get("telegram_bot_token"):
        tok = doc["telegram_bot_token"]
        doc["telegram_bot_token"] = tok[:8] + "•" * 20 + tok[-4:] if len(tok) > 12 else "****"
        doc["has_telegram_token"] = True
    else:
        doc["has_telegram_token"] = False
    # Ensure reminder_periods is always a list
    if "reminder_periods" not in doc:
        doc["reminder_periods"] = [doc.get("reminder_days", 3)]
    return doc


@api_router.put("/settings")
async def update_app_settings(settings: NotificationSettingsModel):
    update_doc = settings.model_dump()

    # If Resend key is masked (unchanged), don't overwrite
    key = update_doc.get("resend_api_key") or ""
    if "****" in key or "•" in key:
        update_doc.pop("resend_api_key", None)

    # If Telegram token is masked (unchanged), don't overwrite
    tok = update_doc.get("telegram_bot_token") or ""
    if "****" in tok or "•" in tok:
        update_doc.pop("telegram_bot_token", None)

    existing = await db.app_settings.find_one({}, {"_id": 0})
    if existing:
        await db.app_settings.update_one({}, {"$set": update_doc})
    else:
        await db.app_settings.insert_one(update_doc)

    saved = await db.app_settings.find_one({}, {"_id": 0})
    if saved:
        if saved.get("resend_api_key"):
            k = saved["resend_api_key"]
            saved["resend_api_key"] = "re_" + "•" * 20 + k[-4:] if len(k) > 4 else "****"
            saved["has_resend_key"] = True
        else:
            saved["has_resend_key"] = False
        if saved.get("telegram_bot_token"):
            t = saved["telegram_bot_token"]
            saved["telegram_bot_token"] = t[:8] + "•" * 20 + t[-4:] if len(t) > 12 else "****"
            saved["has_telegram_token"] = True
        else:
            saved["has_telegram_token"] = False
    return saved or {}


# ─── Database Settings ────────────────────────────────────

@api_router.get("/settings/database")
async def get_db_stats():
    global client, db
    try:
        raw = await db.command("dbstats")
        storage_bytes = raw.get("storageSize", 0)
        data_bytes = raw.get("dataSize", 0)
        index_bytes = raw.get("indexSize", 0)
        objects = raw.get("objects", 0)
        collections = raw.get("collections", 0)

        def fmt(b):
            if b < 1024:
                return f"{b} B"
            elif b < 1024 ** 2:
                return f"{b / 1024:.1f} KB"
            return f"{b / (1024 ** 2):.2f} MB"

        is_custom = CUSTOM_DB_FILE.exists()
        current_url = CUSTOM_DB_FILE.read_text().strip() if is_custom else os.environ['MONGO_URL']
        # Mask credentials in URL for display
        display_url = current_url
        if "@" in current_url:
            proto_end = current_url.find("://") + 3
            at_pos = current_url.rfind("@")
            display_url = current_url[:proto_end] + "***:***@" + current_url[at_pos + 1:]

        return {
            "db_name": DB_NAME,
            "collections": collections,
            "objects": objects,
            "data_size": fmt(data_bytes),
            "storage_size": fmt(storage_bytes),
            "index_size": fmt(index_bytes),
            "total_size": fmt(storage_bytes + index_bytes),
            "current_url": display_url,
            "is_custom": is_custom,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas: {e}")


@api_router.post("/settings/database/test")
async def test_db_connection(req: DBConnectRequest):
    try:
        test_client = AsyncIOMotorClient(req.url, serverSelectionTimeoutMS=5000)
        test_db = test_client[DB_NAME]
        await test_db.command("ping")
        test_client.close()
        return {"success": True, "message": "Conexión exitosa"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo conectar: {e}")


@api_router.post("/settings/database/connect")
async def switch_database(req: DBConnectRequest):
    global client, db
    try:
        new_client = AsyncIOMotorClient(req.url, serverSelectionTimeoutMS=5000)
        new_db = new_client[DB_NAME]
        await new_db.command("ping")
        old_client = client
        client = new_client
        db = new_db
        CUSTOM_DB_FILE.write_text(req.url)
        old_client.close()
        logger.info(f"Database switched to: {req.url[:30]}...")
        return {"success": True, "message": "Base de datos cambiada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al conectar: {e}")


@api_router.post("/settings/database/reset")
async def reset_database():
    global client, db
    try:
        original_url = os.environ['MONGO_URL']
        new_client = AsyncIOMotorClient(original_url)
        new_db = new_client[DB_NAME]
        await new_db.command("ping")
        old_client = client
        client = new_client
        db = new_db
        if CUSTOM_DB_FILE.exists():
            CUSTOM_DB_FILE.unlink()
        old_client.close()
        return {"success": True, "message": "Conexión restaurada a la base de datos original"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al restaurar: {e}")


# ─── Reminders (manual trigger) ───────────────────────────

@api_router.get("/notifications/pending")
async def get_pending_notifications():
    settings_doc = await db.app_settings.find_one({}, {"_id": 0})
    days = int(settings_doc.get("reminder_days", 3)) if settings_doc else 3
    today = datetime.now(timezone.utc).date()
    end = (today + timedelta(days=days)).isoformat()
    today_str = today.isoformat()
    cursor = db.reservations.find(
        {"event_date": {"$gte": today_str, "$lte": end}, "status": {"$nin": ["Cancelado", "Completado"]}},
        {"client_name": 1, "event_date": 1, "event_type": 1, "venue": 1, "_id": 1}
    )
    docs = await cursor.to_list(100)
    return [doc_to_dict(d) for d in docs]



@api_router.post("/reminders/test-email")
async def test_email_connection():
    """Send a test email to verify Resend API key and email config — no events needed."""
    try:
        settings_doc = await db.app_settings.find_one({}, {"_id": 0})
        if not settings_doc:
            raise HTTPException(status_code=400, detail="Configura los ajustes primero")

        api_key   = settings_doc.get("resend_api_key")
        admin_email = settings_doc.get("admin_email")
        sender_name = settings_doc.get("sender_name") or "Cinema Productions"

        if not api_key:
            raise HTTPException(status_code=400, detail="Ingresa tu API Key de Resend primero")
        if not admin_email:
            raise HTTPException(status_code=400, detail="Ingresa un Email Destino primero")

        resend_lib.api_key = api_key
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;background:#f8fafc;padding:32px;">
          <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px 16px 0 0;padding:24px 32px;">
            <h1 style="color:#fff;margin:0;font-size:20px;">{sender_name}</h1>
            <p style="color:rgba(255,255,255,0.85);margin:4px 0 0;font-size:14px;">Prueba de conexión de email</p>
          </div>
          <div style="background:#fff;border-radius:0 0 16px 16px;padding:24px 32px;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
            <p style="color:#10b981;font-size:18px;font-weight:bold;margin-top:0;">✓ Conexión exitosa</p>
            <p style="color:#374151;">Tu configuración de email con Resend funciona correctamente.</p>
            <p style="color:#374151;">Los recordatorios automáticos se enviarán a: <strong>{admin_email}</strong></p>
            <p style="color:#9ca3af;font-size:11px;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:16px;">
              {sender_name} — Prueba enviada desde el Sistema de Gestión de Reservas
            </p>
          </div>
        </div>"""
        params = {
            "from": f"{sender_name} <onboarding@resend.dev>",
            "to": [admin_email],
            "subject": f"✓ Prueba de email — {sender_name}",
            "html": html,
        }
        result = await asyncio.to_thread(resend_lib.Emails.send, params)
        return {"success": True, "message": f"Email de prueba enviado a {admin_email}", "id": getattr(result, 'id', str(result))}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"test-email error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al enviar: {str(e)}")


@api_router.post("/reminders/send")
async def trigger_reminders_manual():
    """Manual trigger — send reminder email/push/telegram/ntfy for upcoming events."""
    try:
        settings_doc = await db.app_settings.find_one({}, {"_id": 0})
        if not settings_doc:
            raise HTTPException(status_code=400, detail="Primero configura los ajustes de notificaciones")

        reminder_periods = settings_doc.get("reminder_periods") or [settings_doc.get("reminder_days", 3)]
        today = datetime.now(timezone.utc).date()

        all_events = []
        for days in reminder_periods:
            target = (today + timedelta(days=days)).isoformat()
            cursor = db.reservations.find(
                {
                    "event_date": target,
                    "status": {"$nin": ["Cancelado", "Completado"]},
                },
                {"client_name": 1, "event_date": 1, "event_time": 1, "event_type": 1, "venue": 1, "total_amount": 1, "advance_paid": 1, "_id": 0}
            )
            evs = await cursor.to_list(100)
            for e in evs:
                e["_days_label"] = f"{days} día(s)" if days > 0 else "hoy"
                all_events.append(e)

        await _dispatch_reminders(all_events, f"{len(reminder_periods)} período(s)", settings_doc)

        channels_used = []
        if settings_doc.get("resend_api_key") and settings_doc.get("admin_email"):
            channels_used.append("email")
        if settings_doc.get("telegram_enabled") and settings_doc.get("telegram_bot_token"):
            channels_used.append("telegram")
        if settings_doc.get("ntfy_enabled") and settings_doc.get("ntfy_topic"):
            channels_used.append("ntfy")
        channels_used.append("push")

        msg = f"{len(all_events)} evento(s) encontrado(s) — enviado vía {', '.join(channels_used)}"
        return {
            "success": True,
            "events_found": len(all_events),
            "channels": channels_used,
            "message": msg,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ─── Desktop Package Download ─────────────────────────────

_ENV_TEMPLATE = """# =======================================================
#  CINEMA PRODUCTIONS - Configuracion de Base de Datos
# =======================================================
#
# Opciones para MONGO_URL:
#
#   embedded
#       Base de datos LOCAL sin internet.
#       Los datos se guardan en cinema_data.json (mismo directorio).
#       Recomendado para uso personal en un solo PC.
#
#   mongodb://localhost:27017
#       MongoDB instalado en tu computadora.
#
#   mongodb+srv://usuario:contrasena@cluster.mongodb.net
#       MongoDB Atlas (nube gratuita en mongodb.com/atlas)
#       Accesible desde cualquier dispositivo.
#
# Para cambiar: edita este archivo con el Bloc de Notas, guarda y reinicia la app.
# O ejecuta config.bat para una ventana visual de configuracion.
# O usa la interfaz: Ajustes > Base de Datos > Cambiar conexion MongoDB
#
MONGO_URL=embedded
DB_NAME=cinema_productions
"""

_CONFIG_PY = r'''"""Cinema Productions — Configurador Visual de Base de Datos
Ejecutar: python config.py  (o doble clic en config.bat)
"""
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

ROOT_DIR = Path(__file__).parent
ENV_FILE = ROOT_DIR / ".env"


def _read_env():
    config = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                config[k.strip()] = v.strip()
    return config


def _write_env(mongo_url: str, db_name: str):
    content = (
        "# Cinema Productions - Configuracion de Base de Datos\n"
        "#\n"
        "# Opciones:\n"
        "#   embedded                              Base de datos local (cinema_data.json)\n"
        "#   mongodb://localhost:27017             MongoDB en tu PC\n"
        "#   mongodb+srv://user:pass@cluster       MongoDB Atlas (nube gratuita)\n"
        "#\n"
        "# Edita este archivo con el Bloc de Notas y guarda.\n"
        f"MONGO_URL={mongo_url}\n"
        f"DB_NAME={db_name}\n"
    )
    ENV_FILE.write_text(content, encoding="utf-8")


def main():
    cfg = _read_env()
    current_url = cfg.get("MONGO_URL", "embedded")
    db_name = cfg.get("DB_NAME", "cinema_productions")

    root = tk.Tk()
    root.title("Cinema Productions — Configurar Base de Datos")
    root.resizable(False, False)
    root.configure(bg="#0f0e17")

    W, H = 560, 420
    root.update_idletasks()
    x = (root.winfo_screenwidth() - W) // 2
    y = (root.winfo_screenheight() - H) // 2
    root.geometry(f"{W}x{H}+{x}+{y}")

    # ── Header ──────────────────────────────────────────
    hdr = tk.Frame(root, bg="#4f46e5", height=72)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="CINEMA PRODUCTIONS", font=("Segoe UI", 15, "bold"),
             bg="#4f46e5", fg="white").pack(pady=(14, 0))
    tk.Label(hdr, text="Configuracion de Base de Datos", font=("Segoe UI", 9),
             bg="#4f46e5", fg="#c7d2fe").pack()

    # ── Body ─────────────────────────────────────────────
    body = tk.Frame(root, bg="#0f0e17", padx=28, pady=18)
    body.pack(fill="both", expand=True)

    tk.Label(body, text="URL de conexion MongoDB:", font=("Segoe UI", 10, "bold"),
             bg="#0f0e17", fg="white", anchor="w").pack(fill="x")
    tk.Label(body,
             text='embedded  |  mongodb://localhost:27017  |  mongodb+srv://user:pass@cluster',
             font=("Courier New", 8), bg="#0f0e17", fg="#6b7280", anchor="w").pack(fill="x", pady=(3, 8))

    url_var = tk.StringVar(value=current_url)
    entry = tk.Entry(body, textvariable=url_var, font=("Courier New", 10),
                     bg="#1e1b4b", fg="#c7d2fe", insertbackground="white",
                     relief="flat", bd=8)
    entry.pack(fill="x")
    entry.focus_set()

    # ── Quick buttons ────────────────────────────────────
    qf = tk.Frame(body, bg="#0f0e17")
    qf.pack(fill="x", pady=(10, 0))
    tk.Label(qf, text="Opciones rapidas:", font=("Segoe UI", 9),
             bg="#0f0e17", fg="#9ca3af").pack(side="left", padx=(0, 8))

    for label, val in [
        ("Embebida (local)", "embedded"),
        ("MongoDB local", "mongodb://localhost:27017"),
    ]:
        tk.Button(qf, text=label, command=lambda v=val: url_var.set(v),
                  bg="#1e1b4b", fg="#a5b4fc", font=("Segoe UI", 9),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=4)

    # ── Info box ─────────────────────────────────────────
    ib = tk.Frame(body, bg="#1c1917")
    ib.pack(fill="x", pady=(16, 0))
    tk.Label(ib,
             text="Consejo: tambien puedes abrir el archivo  .env  directamente con el Bloc de Notas y editar MONGO_URL.",
             font=("Segoe UI", 8), bg="#1c1917", fg="#78716c",
             wraplength=480, justify="left", padx=10, pady=8).pack(fill="x")

    # ── Buttons ──────────────────────────────────────────
    bf = tk.Frame(root, bg="#111827", pady=14)
    bf.pack(fill="x")

    def open_notepad():
        import subprocess
        subprocess.Popen(["notepad.exe", str(ENV_FILE)])

    def save():
        url = url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Por favor ingresa una URL de MongoDB.", parent=root)
            return
        _write_env(url, db_name)
        messagebox.showinfo(
            "Guardado",
            f"Configuracion guardada exitosamente.\n\nMONGO_URL = {url}\n\nReinicia la app para aplicar el cambio.",
            parent=root,
        )
        root.destroy()

    tk.Button(bf, text="  Abrir .env en Bloc de Notas  ", command=open_notepad,
              bg="#374151", fg="#d1d5db", font=("Segoe UI", 9),
              relief="flat", padx=12, pady=7, cursor="hand2").pack(side="left", padx=(24, 8))

    tk.Button(bf, text="  Guardar Configuracion  ", command=save,
              bg="#4f46e5", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=16, pady=7, cursor="hand2").pack(side="right", padx=(8, 24))

    root.mainloop()


if __name__ == "__main__":
    main()
'''

_CONFIG_BAT = r"""@echo off
title Cinema Productions - Configuracion
echo.
echo  Abriendo configuracion de Cinema Productions...
echo.
python --version >nul 2>&1
if not errorlevel 1 ( python config.py & goto FIN )
py --version >nul 2>&1
if not errorlevel 1 ( py config.py & goto FIN )
echo  Python no encontrado. Abriendo .env en el Bloc de Notas...
notepad .env
:FIN
"""

_START_BAT = r"""@echo off
title Cinema Productions - Gestor de Reservas
color 0A
cls
echo.
echo  ====================================================
echo    CINEMA PRODUCTIONS  ^|  Gestor de Reservas
echo  ====================================================
echo.
echo  Archivos del paquete:
echo    app.py           Servidor principal
echo    .env             Configuracion de base de datos
echo    config.bat       Cambiar base de datos (abrir ventana)
echo    cinema_data.json Datos guardados localmente
echo  ====================================================
echo.

REM ── CONFIGURACION OPCIONAL (presiona C para configurar) ──
echo  Presiona  C + ENTER  para configurar la base de datos.
echo  Presiona  ENTER       para iniciar directamente.
echo.
set /p CHOICE="  > "
if /i "%CHOICE%"=="C" (
    echo.
    echo  Abriendo configuracion...
    python config.py >nul 2>&1 || py config.py >nul 2>&1 || notepad .env
    echo.
    echo  Configuracion aplicada. Continuando inicio...
    echo.
)

REM ── PASO 1: Verificar Python ─────────────────────────
echo  [1/4] Verificando Python...
python --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=python & goto PYTHON_OK )
py --version >nul 2>&1
if not errorlevel 1 ( set PYTHON=py & goto PYTHON_OK )
echo.
echo  ERROR: Python no esta instalado.
echo  Descargalo desde: https://www.python.org/downloads/
echo  IMPORTANTE: Marca "Add Python to PATH" al instalar.
echo.
pause & exit /b 1

:PYTHON_OK
echo  OK: Python encontrado.

REM ── PASO 2: Instalar dependencias ───────────────────
echo.
echo  [2/4] Instalando/verificando dependencias...
%PYTHON% -m pip install -r requirements.txt -q --no-warn-script-location
echo  OK: Dependencias listas.

REM ── PASO 3: Iniciar servidor ─────────────────────────
echo.
echo  [3/4] Iniciando servidor...
start "Cinema Productions [servidor - no cierres esta ventana]" /min %PYTHON% app.py

echo  Verificando que el servidor este listo (max 25 seg)...
set /a TRIES=0
:WAIT_LOOP
    timeout /t 1 /nobreak >nul
    %PYTHON% -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8001/api/'); sys.exit(0)" >nul 2>&1
    if not errorlevel 1 goto SERVER_READY
    set /a TRIES+=1
    if %TRIES% GEQ 25 goto SERVER_FAILED
    goto WAIT_LOOP

:SERVER_FAILED
echo.
echo  ====================================================
echo   ERROR: El servidor no respondio en 25 segundos.
echo.
echo   Posibles causas:
echo   - Puerto 8001 ocupado (cierra otras copias)
echo   - Error en .env (ejecuta config.bat para revisar)
echo   - Revisa la ventana del servidor para mas detalles
echo  ====================================================
pause & exit /b 1

:SERVER_READY
echo  OK: Servidor verificado y funcionando.

REM ── PASO 4: Abrir navegador ──────────────────────────
echo.
echo  [4/4] Abriendo Cinema Productions en el navegador...
start http://localhost:8001
echo.
echo  ====================================================
echo    URL:    http://localhost:8001
echo    Datos:  cinema_data.json (guardado automaticamente)
echo    Config: ejecuta config.bat para cambiar la BD
echo  ====================================================
echo.
echo  Para CERRAR: cierra la ventana "Cinema Productions [servidor]"
echo.
pause
"""

_START_SH = """#!/bin/bash
clear
echo ""
echo "  =================================================="
echo "   CINEMA PRODUCTIONS | Gestor de Reservas"
echo "  =================================================="
echo ""

echo "  [1/4] Verificando Python..."
if command -v python3 &>/dev/null; then PYTHON=python3
elif command -v python &>/dev/null; then PYTHON=python
else echo "  ERROR: Python3 no instalado. Ver https://www.python.org/downloads/"; exit 1; fi
echo "  OK: Python encontrado."

echo ""
echo "  [2/4] Instalando dependencias..."
$PYTHON -m pip install -r requirements.txt -q
echo "  OK: Dependencias listas."

echo ""
echo "  [3/4] Iniciando servidor..."
$PYTHON app.py &
SERVER_PID=$!

echo "  Verificando servidor (max 25 seg)..."
TRIES=0
while true; do
    sleep 1
    $PYTHON -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/')" 2>/dev/null && break
    TRIES=$((TRIES + 1))
    [ $TRIES -ge 25 ] && echo "  ERROR: El servidor no respondio." && kill $SERVER_PID 2>/dev/null && exit 1
done
echo "  OK: Servidor verificado."

echo ""
echo "  [4/4] Abriendo Cinema Productions..."
command -v xdg-open &>/dev/null && xdg-open http://localhost:8001
command -v open &>/dev/null && open http://localhost:8001

echo ""
echo "  =================================================="
echo "   URL: http://localhost:8001"
echo "   Para cambiar BD: edita el archivo .env"
echo "   Para cerrar: Ctrl+C"
echo "  =================================================="
wait $SERVER_PID
"""

_REQUIREMENTS = """fastapi>=0.100.0
uvicorn[standard]>=0.20.0
motor>=3.0.0
pymongo>=4.0.0
dnspython>=2.3.0
python-dotenv>=1.0.0
pydantic>=2.0.0
resend>=2.0.0
mongomock-motor>=0.0.36
python-multipart>=0.0.9
"""

_README = """CINEMA PRODUCTIONS - Gestor de Reservas
=========================================

INICIO RAPIDO (Windows):
  1. Doble clic en  start.bat
  2. Presiona ENTER para iniciar, o  C + ENTER  para configurar primero
  3. La app se abre automaticamente en el navegador

REQUISITO: Python 3.8+
  https://www.python.org/downloads/
  IMPORTANTE: marcar "Add Python to PATH"

BASE DE DATOS:
  El archivo  .env  controla donde se guardan tus datos.

  OPCIONES:
    MONGO_URL=embedded
      → Base de datos local, SIN internet, datos en cinema_data.json
        Recomendado para uso personal en un solo PC.

    MONGO_URL=mongodb://localhost:27017
      → MongoDB instalado en tu computadora.

    MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net
      → MongoDB Atlas (nube GRATUITA en mongodb.com/atlas)
        Accesible desde cualquier dispositivo.

CAMBIAR BASE DE DATOS (3 formas):
  A) Doble clic en  config.bat  → Ventana visual de configuracion
  B) Abrir  .env  con el Bloc de Notas → Edita MONGO_URL → Guarda
  C) En el start.bat → Presiona C + ENTER antes de iniciar

DATOS AUTOMATICOS:
  En modo embebido, los datos se guardan en  cinema_data.json
  Auto-guardado cada 60 segundos y al cerrar la app.

Cinema Productions - Sistema de Gestion de Reservas
"""


# ─── Gmail OAuth2 Endpoints ───────────────────────────────────
@api_router.get("/oauth/gmail/start")
async def gmail_oauth_start():
    """Return Google OAuth2 authorization URL."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google credentials not configured")
    flow = Flow.from_client_config(
        {"web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }},
        scopes=GMAIL_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return {"url": auth_url}


@api_router.get("/oauth/gmail/callback")
async def gmail_oauth_callback(code: str = None, error: str = None):
    """Exchange auth code for tokens and store refresh_token."""
    if error or not code:
        return RedirectResponse(url=f"https://event-reserve-pro-5.preview.emergentagent.com/ajustes?gmail_error={error or 'cancelled'}")
    try:
        flow = Flow.from_client_config(
            {"web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI],
            }},
            scopes=GMAIL_SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        # Get user email
        service = build("oauth2", "v2", credentials=creds)
        user_info = await asyncio.to_thread(service.userinfo().get().execute)
        user_email = user_info.get("email", "")
        # Store tokens
        await db.oauth_tokens.update_one(
            {"provider": "gmail"},
            {"$set": {
                "provider": "gmail",
                "email": user_email,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "connected_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        logger.info(f"Gmail connected: {user_email}")
        return RedirectResponse(url="https://event-reserve-pro-5.preview.emergentagent.com/ajustes?gmail_ok=1")
    except Exception as e:
        logger.error(f"Gmail OAuth callback error: {e}")
        return RedirectResponse(url=f"https://event-reserve-pro-5.preview.emergentagent.com/ajustes?gmail_error={str(e)[:60]}")


@api_router.get("/oauth/gmail/status")
async def gmail_status():
    doc = await db.oauth_tokens.find_one({"provider": "gmail"}, {"_id": 0})
    if doc and doc.get("refresh_token"):
        return {"connected": True, "email": doc.get("email", ""), "connected_at": doc.get("connected_at")}
    return {"connected": False, "email": "", "connected_at": None}


@api_router.delete("/oauth/gmail/disconnect")
async def gmail_disconnect():
    await db.oauth_tokens.delete_one({"provider": "gmail"})
    return {"ok": True}


@api_router.post("/oauth/gmail/test")
async def gmail_test():
    """Send a test email to verify Gmail connection."""
    doc = await db.oauth_tokens.find_one({"provider": "gmail"}, {"_id": 0})
    if not doc or not doc.get("refresh_token"):
        raise HTTPException(status_code=400, detail="Gmail no conectado")
    try:
        html = """
        <div style='font-family:sans-serif;padding:20px'>
          <h2 style='color:#6366f1'>Cinema Productions — Prueba de correo ✓</h2>
          <p>Este es un correo de prueba enviado automáticamente desde tu app de reservas.</p>
          <p>Si lo recibes, los recordatorios automáticos funcionarán correctamente.</p>
        </div>"""
        await _send_gmail(to=doc["email"], subject="✓ Prueba — Cinema Productions", html=html)
        return {"ok": True, "message": f"Correo enviado a {doc['email']}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Web Push Endpoints ───────────────────────────────────────
@api_router.get("/push/vapid-key")
async def get_vapid_key():
    return {"publicKey": VAPID_PUBLIC_KEY}


class PushSubscriptionModel(BaseModel):
    endpoint: str
    expirationTime: Optional[float] = None
    keys: dict


@api_router.post("/push/subscribe")
async def push_subscribe(sub: PushSubscriptionModel):
    await db.push_subscriptions.update_one(
        {"endpoint": sub.endpoint},
        {"$set": {
            "endpoint": sub.endpoint,
            "keys": sub.keys,
            "subscribed_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True}


@api_router.delete("/push/unsubscribe")
async def push_unsubscribe(endpoint: str):
    await db.push_subscriptions.delete_one({"endpoint": endpoint})
    return {"ok": True}


@api_router.post("/push/test")
async def push_test():
    """Send a test push notification to all subscribers."""
    try:
        await _send_push_to_all(
            title="Cinema Productions — Prueba ✓",
            body="Las notificaciones de escritorio están funcionando.",
            url="/dashboard",
        )
        count = await db.push_subscriptions.count_documents({})
        return {"ok": True, "sent_to": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/telegram/test")
async def telegram_test():
    """Send a test Telegram message. Returns 200 always (K8s ingress strips 4xx bodies)."""
    doc = await db.app_settings.find_one({}, {"_id": 0})
    if not doc or not doc.get("telegram_bot_token") or not doc.get("telegram_chat_id"):
        return {"ok": False, "error": "Configura el token y chat_id de Telegram primero"}
    try:
        await _send_telegram(
            doc["telegram_bot_token"],
            doc["telegram_chat_id"],
            "<b>Cinema Productions</b> — Prueba ✓\n\nTelegram conectado correctamente. Recibirás los recordatorios de eventos aquí.",
        )
        return {"ok": True, "message": "Mensaje enviado a Telegram"}
    except Exception as e:
        return {"ok": False, "error": f"Error de Telegram: {e}"}


@api_router.post("/ntfy/test")
async def ntfy_test():
    """Send a test ntfy.sh notification. Returns 200 always (K8s ingress strips 4xx bodies)."""
    doc = await db.app_settings.find_one({}, {"_id": 0})
    if not doc or not doc.get("ntfy_topic"):
        return {"ok": False, "error": "Configura el tema de ntfy primero"}
    try:
        await _send_ntfy(
            doc["ntfy_topic"],
            "Cinema Productions — Prueba ✓",
            "ntfy conectado correctamente. Recibirás los recordatorios de eventos aquí.",
            priority="high",
        )
        return {"ok": True, "message": f"Notificación enviada al tema: {doc['ntfy_topic']}"}
    except Exception as e:
        return {"ok": False, "error": f"Error de ntfy: {e}"}



_build_state = {"status": "idle", "message": "Listo para actualizar", "started_at": None, "finished_at": None}


async def _run_frontend_build():
    global _build_state
    try:
        frontend_dir = str(ROOT_DIR.parent / "frontend")
        process = await asyncio.create_subprocess_exec(
            "yarn", "build",
            cwd=frontend_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **os.environ,
                "CI": "false",
                "GENERATE_SOURCEMAP": "false",
                "REACT_APP_BACKEND_URL": "http://localhost:8001",
                "PUBLIC_URL": "/",
            },
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        if process.returncode == 0:
            _build_state = {
                "status": "ready",
                "message": "App actualizada correctamente. Ya puedes descargarla.",
                "started_at": _build_state["started_at"],
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info("Frontend build completed successfully")
        else:
            err = stderr.decode("utf-8", errors="replace")[:300]
            _build_state = {
                "status": "error",
                "message": f"Error en la compilación: {err}",
                "started_at": _build_state["started_at"],
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.error(f"Frontend build failed: {err}")
    except asyncio.TimeoutError:
        _build_state = {**_build_state, "status": "error", "message": "Tiempo de espera agotado (5 min). Inténtalo de nuevo."}
    except Exception as e:
        _build_state = {**_build_state, "status": "error", "message": f"Error inesperado: {str(e)}"}


@api_router.post("/download/package/rebuild")
async def rebuild_package():
    global _build_state
    if _build_state["status"] == "building":
        return {"status": "building", "message": "Ya hay una compilación en progreso. Por favor espera."}
    _build_state = {
        "status": "building",
        "message": "Compilando la app con los últimos cambios… esto tarda 1–3 minutos.",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    asyncio.create_task(_run_frontend_build())
    return _build_state


@api_router.get("/download/package/build-status")
async def get_build_status():
    return _build_state


@api_router.get("/download/package")
async def download_package(request: Request):
    import zipfile

    build_dir = ROOT_DIR.parent / "frontend" / "build"
    if not build_dir.exists():
        raise HTTPException(
            status_code=503,
            detail="El paquete aun no esta listo. Espera 2 minutos e intentalo de nuevo."
        )

    cloud_url = str(request.base_url).rstrip("/")
    standalone_py = (ROOT_DIR / 'standalone_app.py').read_text()

    # Auto-version based on timestamp
    auto_version = datetime.now(timezone.utc).strftime("%Y.%m.%d.%H%M")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('cinema-productions/app.py', standalone_py)
        zf.writestr('cinema-productions/.env', _ENV_TEMPLATE)
        zf.writestr('cinema-productions/config.py', _CONFIG_PY)
        zf.writestr('cinema-productions/config.bat', _CONFIG_BAT)
        zf.writestr('cinema-productions/requirements.txt', _REQUIREMENTS)
        zf.writestr('cinema-productions/start.bat', _START_BAT)
        zf.writestr('cinema-productions/start.sh', _START_SH)
        zf.writestr('cinema-productions/README.txt', _README)
        # Embed cloud URL + this version so Desktop App knows its own version
        zf.writestr('cinema-productions/update_server_url.txt', cloud_url)
        zf.writestr('cinema-productions/version.txt', auto_version)

        for file_path in sorted(build_dir.rglob('*')):
            if file_path.is_file():
                arc_name = 'cinema-productions/build/' + str(file_path.relative_to(build_dir))
                zf.write(str(file_path), arc_name)

    zip_bytes = buf.getvalue()
    filename = f"cinema-productions-{auto_version}.zip"
    safe_name = f"auto_{auto_version.replace('.', '_')}.zip"
    file_path = UPDATES_DIR / safe_name
    file_path.write_bytes(zip_bytes)

    # Auto-register this version in the shared MongoDB database
    await db.app_updates.update_many({}, {"$set": {"is_latest": False}})
    update_doc = {
        "version": auto_version,
        "filename": filename,
        "stored_name": safe_name,
        "notes": "Generada automáticamente al descargar desde Ajustes",
        "channel": "stable",
        "file_size": len(zip_bytes),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_latest": True,
        "download_url": f"{cloud_url}/api/updates/download",
    }
    await db.app_updates.insert_one(update_doc)

    return Response(
        content=zip_bytes,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )




# ── APP UPDATES ──────────────────────────────────────────────────────────────

@api_router.post("/updates/upload")
async def upload_app_update(
    file: UploadFile = File(...),
    version: str = Form(...),
    notes: str = Form(""),
    channel: str = Form("stable"),
):
    content = await file.read()
    file_id = str(uuid.uuid4())
    safe_name = f"{file_id}_{file.filename}"
    file_path = UPDATES_DIR / safe_name
    file_path.write_bytes(content)

    # Mark all previous as not latest
    await db.app_updates.update_many({}, {"$set": {"is_latest": False}})

    doc = {
        "version": version,
        "filename": file.filename,
        "stored_name": safe_name,
        "notes": notes,
        "channel": channel,
        "file_size": len(content),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_latest": True,
    }
    result = await db.app_updates.insert_one(doc)
    return {**{k: v for k, v in doc.items() if k != "_id"}, "id": str(result.inserted_id)}


@api_router.get("/updates/latest")
async def get_latest_update():
    doc = await db.app_updates.find_one({"is_latest": True}, sort=[("created_at", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No hay actualizaciones disponibles")
    return {
        "id": str(doc["_id"]),
        "version": doc["version"],
        "filename": doc["filename"],
        "notes": doc.get("notes", ""),
        "channel": doc.get("channel", "stable"),
        "file_size": doc["file_size"],
        "created_at": doc["created_at"],
    }


@api_router.get("/updates/history")
async def get_update_history():
    cursor = db.app_updates.find({}, sort=[("created_at", -1)])
    docs = await cursor.to_list(200)
    return [
        {
            "id": str(d["_id"]),
            "version": d["version"],
            "filename": d["filename"],
            "notes": d.get("notes", ""),
            "channel": d.get("channel", "stable"),
            "file_size": d["file_size"],
            "created_at": d["created_at"],
            "is_latest": d.get("is_latest", False),
        }
        for d in docs
    ]


@api_router.get("/updates/download")
async def download_latest_update():
    """Download the currently active (is_latest) update file."""
    doc = await db.app_updates.find_one({"is_latest": True}, sort=[("created_at", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No hay actualización activa")
    file_path = UPDATES_DIR / doc["stored_name"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

    def iter_file():
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'},
    )


@api_router.get("/updates/download/{update_id}")
async def download_update(update_id: str):
    try:
        oid = ObjectId(update_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await db.app_updates.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Actualización no encontrada")
    file_path = UPDATES_DIR / doc["stored_name"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

    def iter_file():
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'},
    )


@api_router.put("/updates/{update_id}/set-latest")
async def set_latest_update(update_id: str):
    try:
        oid = ObjectId(update_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    await db.app_updates.update_many({}, {"$set": {"is_latest": False}})
    result = await db.app_updates.update_one({"_id": oid}, {"$set": {"is_latest": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Actualización no encontrada")
    return {"message": "Versión marcada como activa"}


@api_router.delete("/updates/{update_id}")
async def delete_update(update_id: str):
    try:
        oid = ObjectId(update_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await db.app_updates.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Actualización no encontrada")
    file_path = UPDATES_DIR / doc["stored_name"]
    if file_path.exists():
        file_path.unlink()
    await db.app_updates.delete_one({"_id": oid})
    # If deleted was the latest, promote the next most recent
    if doc.get("is_latest"):
        newer = await db.app_updates.find_one({}, sort=[("created_at", -1)])
        if newer:
            await db.app_updates.update_one({"_id": newer["_id"]}, {"$set": {"is_latest": True}})
    return {"message": "Actualización eliminada"}


@api_router.get("/updates/check")
async def check_updates_cloud():
    """Cloud version is always the source of truth → always up to date."""
    doc = await db.app_updates.find_one({"is_latest": True}, sort=[("created_at", -1)])
    if not doc:
        return {"checked": True, "has_update": False, "is_cloud": True, "remote_version": None}
    return {
        "checked": True,
        "has_update": False,
        "is_cloud": True,
        "id": str(doc["_id"]),
        "remote_version": doc["version"],
        "local_version": doc["version"],
        "filename": doc["filename"],
        "notes": doc.get("notes", ""),
        "created_at": doc["created_at"],
    }


@api_router.post("/updates/dismiss")
async def dismiss_update_cloud():
    return {"message": "OK"}


# ── APPEARANCE CLOUD SYNC ────────────────────────────────────────────────────

@api_router.get("/settings/appearance")
async def get_appearance_snapshot():
    doc = await db.app_settings.find_one({}, {"_id": 0, "appearance_snapshot": 1, "appearance_updated_at": 1})
    doc = doc or {}
    return {"snapshot": doc.get("appearance_snapshot"), "updated_at": doc.get("appearance_updated_at")}


@api_router.put("/settings/appearance")
async def save_appearance_snapshot(payload: dict = Body(...)):
    snapshot = payload.get("snapshot") or {}
    updated_at = datetime.now(timezone.utc).isoformat()
    await db.app_settings.update_one(
        {},
        {"$set": {"appearance_snapshot": snapshot, "appearance_updated_at": updated_at}},
        upsert=True,
    )
    return {"updated_at": updated_at}


# ── SAVED THEMES ─────────────────────────────────────────────────────────────

@api_router.get("/themes")
async def list_saved_themes():
    docs = await db.saved_themes.find({}, sort=[("created_at", -1)]).to_list(200)
    return [
        {"id": str(d["_id"]), "name": d["name"], "snapshot": d.get("snapshot", {}), "created_at": d["created_at"]}
        for d in docs
    ]


@api_router.post("/themes")
async def create_saved_theme(payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del tema es requerido")
    doc = {
        "name": name,
        "snapshot": payload.get("snapshot") or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.saved_themes.insert_one(doc)
    return {"id": str(result.inserted_id), "name": name, "created_at": doc["created_at"]}


@api_router.delete("/themes/{theme_id}")
async def delete_saved_theme(theme_id: str):
    try:
        oid = ObjectId(theme_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    result = await db.saved_themes.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return {"message": "Tema eliminado"}


# ── APP SECURITY (password lock + page protection) ──────────────────────────

PBKDF2_ITERATIONS = 260000


def _hash_app_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def _verify_app_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


@api_router.get("/security/status")
async def get_security_status():
    doc = await db.app_settings.find_one({}, {"_id": 0, "app_password_hash": 1, "app_password_hint": 1, "page_protection_enabled": 1}) or {}
    return {
        "password_enabled": bool(doc.get("app_password_hash")),
        "hint": doc.get("app_password_hint") or "",
        "protection_enabled": bool(doc.get("page_protection_enabled")),
    }


@api_router.post("/security/set-password")
async def set_app_password_endpoint(payload: dict = Body(...)):
    password = (payload.get("password") or "").strip()
    hint = (payload.get("hint") or "").strip()
    current = payload.get("current_password") or ""
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 4 caracteres")
    doc = await db.app_settings.find_one({}, {"app_password_hash": 1}) or {}
    if doc.get("app_password_hash") and not _verify_app_password(current, doc["app_password_hash"]):
        raise HTTPException(status_code=401, detail="La contraseña actual es incorrecta")
    await db.app_settings.update_one(
        {},
        {"$set": {"app_password_hash": _hash_app_password(password), "app_password_hint": hint}},
        upsert=True,
    )
    return {"message": "Contraseña guardada"}


@api_router.post("/security/verify")
async def verify_app_password_endpoint(payload: dict = Body(...)):
    doc = await db.app_settings.find_one({}, {"app_password_hash": 1}) or {}
    if not doc.get("app_password_hash"):
        return {"valid": True}
    if not _verify_app_password(payload.get("password") or "", doc["app_password_hash"]):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    return {"valid": True}


@api_router.post("/security/remove-password")
async def remove_app_password_endpoint(payload: dict = Body(...)):
    doc = await db.app_settings.find_one({}, {"app_password_hash": 1}) or {}
    if not doc.get("app_password_hash"):
        raise HTTPException(status_code=400, detail="No hay contraseña configurada")
    if not _verify_app_password(payload.get("current_password") or "", doc["app_password_hash"]):
        raise HTTPException(status_code=401, detail="La contraseña actual es incorrecta")
    await db.app_settings.update_one({}, {"$unset": {"app_password_hash": "", "app_password_hint": ""}})
    return {"message": "Contraseña eliminada"}


@api_router.put("/security/protection")
async def set_page_protection_endpoint(payload: dict = Body(...)):
    enabled = bool(payload.get("enabled"))
    await db.app_settings.update_one({}, {"$set": {"page_protection_enabled": enabled}}, upsert=True)
    return {"enabled": enabled}


# ═══════════════════════════════════════════════════════════════════
# GitHub Integration & AI Context (Continuity for next AI)
# ═══════════════════════════════════════════════════════════════════
import subprocess
import re as _re

REPO_ROOT = Path(__file__).parent.parent  # /app

DEFAULT_AI_CONTEXT = """# 🧠 CONTEXTO PARA LA PRÓXIMA IA — Cinema Productions

## 📌 Descripción del Proyecto
**Cinema Productions** es un sistema completo de gestión de reservas de eventos para empresas de producción audiovisual. Los clientes dan un anticipo por una fecha específica y se gestiona todo el ciclo: reservas, pagos, calendario, socios, notificaciones multi-canal y respaldos.

## 🏗️ Arquitectura
- **Frontend**: React 19 + TailwindCSS + Framer Motion + Shadcn UI (craco)
- **Backend**: FastAPI (Python) + Motor (MongoDB async) + APScheduler
- **DB**: MongoDB (colecciones: reservations, socios, app_settings, themes)
- **Repo Git**: /app está inicializado como repo git, remoto = GitHub

## 📁 Estructura de archivos clave
```
/app/
├── backend/
│   ├── server.py             # FastAPI principal (~2700 líneas)
│   ├── standalone_app.py     # Versión desktop embebida
│   ├── requirements.txt
│   ├── .env                  # MONGO_URL, DB_NAME, CORS_ORIGINS
│   ├── backups/              # Auto-backups JSON
│   └── uploads/updates/      # .exe/zip de actualizaciones
├── frontend/
│   ├── src/
│   │   ├── App.js            # Router con transiciones dinámicas
│   │   ├── context/SettingsContext.jsx   # Estado global apariencia
│   │   ├── pages/            # Dashboard, Reservations, CalendarView, Socios,
│   │   │                     # DatabasePage, AppearancePage, Settings, UpdatesPage
│   │   ├── components/       # Layout (sidebar), forms, secciones
│   │   ├── lib/api.js        # Axios configurado con REACT_APP_BACKEND_URL
│   │   └── hooks/            # useNotifications, useAutoBackup, use-toast
│   ├── .env                  # REACT_APP_BACKEND_URL
│   └── package.json
└── memory/PRD.md             # PRD original
```

## 🔧 Variables de Entorno CRÍTICAS
- `backend/.env`: `MONGO_URL`, `DB_NAME`, `CORS_ORIGINS`
- `frontend/.env`: `REACT_APP_BACKEND_URL` (URL externa a través de Kubernetes ingress)
- **NUNCA** modificar estas variables ni hardcodear URLs/puertos
- Backend se sirve por supervisor en `0.0.0.0:8001`
- Todas las rutas backend deben tener prefijo `/api`

## 🚀 Comandos de servicio
```bash
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
sudo supervisorctl restart all
sudo supervisorctl status
```

## 🎯 Funcionalidades Implementadas
### Core
- CRUD Reservas con anticipo/balance/fecha-evento (`/api/reservations`)
- Calendario mensual con filtros (`/api/calendar`)
- Dashboard con estadísticas y gráficos (`/api/stats`, `/api/financials`)
- Gestión de Socios/equipo (`/api/socios`)

### Apariencia (9 secciones en AppearancePage.jsx)
Paleta de colores, tipografía, animaciones, formas/bordes, fondos, interfaz/espacio, tipos de evento, PDF, logo

### Notificaciones Multi-canal
- Email vía **Resend** (`/api/reminders/*`)
- **Gmail OAuth** (`/api/oauth/gmail/*`)
- **Telegram Bot** (`/api/telegram/*`)
- **ntfy.sh** (`/api/ntfy/*`)
- **Web Push VAPID** (`/api/push/*`)
- WhatsApp link automático

### Base de Datos (`/api/backup/*`, `/api/data/*`)
- JSON backup/restore
- Auto-backup con APScheduler
- CSV/Excel import/export
- Cambio dinámico de MongoDB URL

### GitHub & Actualizaciones (NUEVO)
- `/api/github/config` — guardar URL repo + token opcional
- `/api/github/check-updates` — compara commits con GitHub API
- `/api/github/apply-update` — ejecuta `git pull` y refleja cambios
- `/api/ai-context` — GET/POST este mismo contexto (auto-persistente)

### Seguridad
- Contraseña de app (`/api/security/*`) con bcrypt
- Protección por página

## 🔑 Integraciones que requieren claves (opcionales)
Guardadas en `app_settings` MongoDB:
- `google_client_id`, `google_client_secret` (Gmail OAuth)
- `resend_api_key` (email)
- `telegram_bot_token`, `telegram_chat_id`
- `ntfy_topic`
- `vapid_public_key`, `vapid_private_key`
- `github_repo_url`, `github_token` (opcional para repos privados)

## 📚 Modelos MongoDB principales
### `reservations`
```json
{
  "id": "uuid", "client_name", "client_phone", "event_type",
  "event_date": "YYYY-MM-DD", "total_amount", "advance_amount",
  "balance", "package", "status", "notes", "receipts": [...],
  "created_at", "updated_at"
}
```

### `socios`
```json
{ "id": "uuid", "name", "role", "phone", "email", "photo_base64" }
```

### `app_settings` (documento único)
Contiene TODO: configuración de negocio, apariencia, integraciones, credenciales.

## ⚠️ Reglas críticas para trabajar en este código
1. **NUNCA** usar `ObjectId` de MongoDB — SIEMPRE UUIDs (`str(uuid.uuid4())`)
2. **NUNCA** modificar valores en `.env`
3. **SIEMPRE** prefijar rutas backend con `/api`
4. Frontend usa `import.meta.env.REACT_APP_BACKEND_URL` o `process.env.REACT_APP_BACKEND_URL`
5. No hardcodear URLs ni puertos
6. Al editar archivos existentes: usar `search_replace`, no reescribir
7. Al agregar deps Python: actualizar `requirements.txt` y reinstalar
8. Al agregar deps JS: usar `yarn add` (nunca npm)
9. Hot reload activo — solo reiniciar si se cambia `.env` o se instalan deps

## 🧪 Testing
- Backend tests en `/app/backend/tests/`
- Testing agent: `deep_testing_backend_v2`
- Frontend testing: `auto_frontend_testing_agent`
- `test_result.md` en raíz — protocolo de comunicación entre agentes

## 🗂️ Cómo se conecta el repositorio GitHub
El usuario configura la URL desde `DatabasePage.jsx` → sección "GitHub & Contexto IA".
Se guarda en `app_settings.github_config`. Al pulsar "Buscar actualizaciones" en
`UpdatesPage.jsx`, el backend compara el SHA del commit local con el remoto vía
GitHub API pública (`/repos/{owner}/{repo}/commits`). Si hay cambios, ejecuta
`git -C /app fetch && git -C /app reset --hard origin/main` y reinicia servicios.

---
**Última actualización de este contexto**: se auto-actualiza al guardar cambios.
"""


def _parse_github_url(url: str):
    """Extrae owner/repo de una URL de GitHub."""
    if not url:
        return None, None
    m = _re.match(r"^https?://github\.com/([^/]+)/([^/.]+?)(?:\.git)?/?$", url.strip())
    if not m:
        return None, None
    return m.group(1), m.group(2)


async def _get_github_config():
    doc = await db.app_settings.find_one({}, {"github_config": 1}) or {}
    return doc.get("github_config") or {}


@api_router.get("/github/config")
async def get_github_config():
    cfg = await _get_github_config()
    # No devolver el token completo por seguridad
    return {
        "repo_url": cfg.get("repo_url", ""),
        "has_token": bool(cfg.get("token")),
        "last_commit_sha": cfg.get("last_commit_sha", ""),
        "last_check_at": cfg.get("last_check_at", ""),
        "branch": cfg.get("branch", "main"),
    }


@api_router.post("/github/config")
async def save_github_config(payload: dict = Body(...)):
    repo_url = (payload.get("repo_url") or "").strip()
    token = (payload.get("token") or "").strip()
    branch = (payload.get("branch") or "main").strip()

    owner, repo = _parse_github_url(repo_url)
    if repo_url and not owner:
        raise HTTPException(status_code=400, detail="URL de GitHub inválida. Formato esperado: https://github.com/usuario/repo")

    update = {"repo_url": repo_url, "branch": branch}
    if token:
        update["token"] = token
    elif payload.get("clear_token"):
        update["token"] = ""

    await db.app_settings.update_one(
        {},
        {"$set": {f"github_config.{k}": v for k, v in update.items()}},
        upsert=True
    )

    # Intentar sincronizar el remoto del repo local
    if repo_url:
        try:
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "remote", "set-url", "origin", repo_url],
                capture_output=True, timeout=10, check=False
            )
        except Exception as e:
            logger.warning(f"No se pudo actualizar remote: {e}")

    return {"success": True, "repo_url": repo_url, "branch": branch}


def _get_local_commit_sha():
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Error obteniendo SHA local: {e}")
    return ""


@api_router.get("/github/check-updates")
async def check_github_updates():
    cfg = await _get_github_config()
    repo_url = cfg.get("repo_url", "")
    if not repo_url:
        raise HTTPException(status_code=400, detail="No hay repositorio de GitHub configurado")

    owner, repo = _parse_github_url(repo_url)
    if not owner:
        raise HTTPException(status_code=400, detail="URL de GitHub inválida")

    branch = cfg.get("branch") or "main"
    token = cfg.get("token", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    local_sha = _get_local_commit_sha()

    # Obtener commits del remoto
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    async with httpx.AsyncClient(timeout=15) as http:
        try:
            r = await http.get(api_url, headers=headers, params={"sha": branch, "per_page": 20})
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error conectando a GitHub: {e}")

    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Repositorio no encontrado (¿es privado y falta token?)")
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="Token de GitHub inválido o insuficiente")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub API respondió {r.status_code}: {r.text[:200]}")

    commits_data = r.json()
    if not commits_data:
        return {"has_updates": False, "commits": [], "local_sha": local_sha, "remote_sha": "", "branch": branch}

    remote_sha = commits_data[0]["sha"]

    # Determinar si hay updates: local_sha debe encontrarse en la lista de commits del remoto
    # Si local está en la lista, contamos cuántos hay ANTES (más nuevos) que él
    local_found_at = -1
    for i, c in enumerate(commits_data):
        if c["sha"] == local_sha:
            local_found_at = i
            break

    if local_found_at == 0:
        # Local == remote latest → nada nuevo
        has_updates = False
        new_commits = []
    elif local_found_at > 0:
        # Hay `local_found_at` commits nuevos en el remoto
        has_updates = True
        new_commits_data = commits_data[:local_found_at]
    else:
        # Local no está en la lista: puede estar adelantado o divergente.
        # Solo marcamos updates si el remoto tiene un SHA distinto Y no encontramos el local.
        # Para ser conservadores, si local_sha existe (no vacío) y no aparece en top 20, asumimos divergencia
        # y marcamos has_updates SOLO si no hay local_sha (primera vez)
        has_updates = bool(remote_sha) and (not local_sha)
        new_commits_data = commits_data if has_updates else []

    new_commits = []
    if has_updates:
        for c in (new_commits_data if 'new_commits_data' in locals() else commits_data[:5]):
            commit_info = c.get("commit", {})
            author = commit_info.get("author", {})
            new_commits.append({
                "sha": c["sha"][:7],
                "full_sha": c["sha"],
                "message": (commit_info.get("message") or "").split("\n")[0][:200],
                "author": author.get("name", "desconocido"),
                "date": author.get("date", ""),
                "url": c.get("html_url", "")
            })

    # Guardar último chequeo
    await db.app_settings.update_one(
        {},
        {"$set": {
            "github_config.last_check_at": datetime.now(timezone.utc).isoformat(),
            "github_config.last_remote_sha": remote_sha,
        }},
        upsert=True
    )

    return {
        "has_updates": has_updates,
        "local_sha": local_sha,
        "local_sha_short": local_sha[:7] if local_sha else "",
        "remote_sha": remote_sha,
        "remote_sha_short": remote_sha[:7],
        "branch": branch,
        "commits_ahead": len(new_commits),
        "commits": new_commits,
        "repo_url": repo_url,
    }


@api_router.post("/github/apply-update")
async def apply_github_update(payload: dict = Body(default={})):
    cfg = await _get_github_config()
    repo_url = cfg.get("repo_url", "")
    if not repo_url:
        raise HTTPException(status_code=400, detail="No hay repositorio configurado")

    branch = cfg.get("branch") or "main"
    force = bool(payload.get("force", True))  # por defecto reset --hard

    logs = []
    try:
        # 1. Fetch
        fetch = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "fetch", "origin", branch],
            capture_output=True, text=True, timeout=60
        )
        logs.append(f"$ git fetch origin {branch}\n{fetch.stdout}{fetch.stderr}")
        if fetch.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error en git fetch: {fetch.stderr}")

        # 2. Reset o pull
        if force:
            reset = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "reset", "--hard", f"origin/{branch}"],
                capture_output=True, text=True, timeout=60
            )
            logs.append(f"$ git reset --hard origin/{branch}\n{reset.stdout}{reset.stderr}")
            if reset.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Error en git reset: {reset.stderr}")
        else:
            pull = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "pull", "origin", branch],
                capture_output=True, text=True, timeout=60
            )
            logs.append(f"$ git pull origin {branch}\n{pull.stdout}{pull.stderr}")
            if pull.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Error en git pull: {pull.stderr}")

        new_sha = _get_local_commit_sha()
        await db.app_settings.update_one(
            {},
            {"$set": {
                "github_config.last_commit_sha": new_sha,
                "github_config.last_update_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True
        )

        # 3. Reiniciar servicios en background (para reflejar cambios)
        async def _restart_later():
            await asyncio.sleep(2)
            try:
                subprocess.run(["sudo", "supervisorctl", "restart", "frontend"], timeout=30, capture_output=True)
                subprocess.run(["sudo", "supervisorctl", "restart", "backend"], timeout=30, capture_output=True)
            except Exception as e:
                logger.warning(f"Error reiniciando servicios: {e}")

        asyncio.create_task(_restart_later())

        return {
            "success": True,
            "new_sha": new_sha,
            "new_sha_short": new_sha[:7] if new_sha else "",
            "logs": "\n".join(logs),
            "message": "Actualización aplicada. Los servicios se reiniciarán en 2 segundos.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error aplicando actualización: {e}")


# ─── AI Context (contexto para la próxima IA) ─────────────────
@api_router.get("/ai-context")
async def get_ai_context():
    doc = await db.app_settings.find_one({}, {"ai_context": 1}) or {}
    ctx = doc.get("ai_context") or {}
    if not ctx.get("content"):
        # Inicializar con el contexto por defecto
        await db.app_settings.update_one(
            {},
            {"$set": {"ai_context": {
                "content": DEFAULT_AI_CONTEXT,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}},
            upsert=True
        )
        return {"content": DEFAULT_AI_CONTEXT, "updated_at": datetime.now(timezone.utc).isoformat(), "is_default": True}
    return {
        "content": ctx.get("content", ""),
        "updated_at": ctx.get("updated_at", ""),
        "is_default": False,
    }


@api_router.post("/ai-context")
async def save_ai_context(payload: dict = Body(...)):
    content = payload.get("content", "")
    if not isinstance(content, str):
        raise HTTPException(status_code=400, detail="content debe ser string")
    await db.app_settings.update_one(
        {},
        {"$set": {"ai_context": {
            "content": content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}},
        upsert=True
    )
    return {"success": True, "updated_at": datetime.now(timezone.utc).isoformat()}


@api_router.post("/ai-context/reset")
async def reset_ai_context():
    await db.app_settings.update_one(
        {},
        {"$set": {"ai_context": {
            "content": DEFAULT_AI_CONTEXT,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}},
        upsert=True
    )
    return {"success": True, "content": DEFAULT_AI_CONTEXT}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
