"""
Email 通知模組
支援 SMTP 或 Resend API 發送課程監控通知信件

Resend API（優先，適用 Railway 等限制 SMTP 的環境）：
  RESEND_API_KEY   Resend API Key（設定後優先使用）
  RESEND_FROM      寄件者（預設 NTUST Monitor <onboarding@resend.dev>，需自訂網域可改）

SMTP（備援）：
  SMTP_HOST      SMTP 伺服器位址（預設 smtp.gmail.com）
  SMTP_PORT      SMTP 埠號（預設 587）
  SMTP_USERNAME  寄件者 Email（同時作為帳號）
  SMTP_PASSWORD  SMTP 密碼（Gmail 請使用應用程式密碼）
"""

import os
import smtplib
import logging
import threading
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from ..logging_setup import get_logger

logger = get_logger(__name__)


class EmailSender:
    def __init__(self):
        self.resend_api_key = (os.getenv('RESEND_API_KEY') or '').strip()
        self.resend_from = (os.getenv('RESEND_FROM') or 'NTUST Monitor <onboarding@resend.dev>').strip()
        self.use_resend = bool(self.resend_api_key)

        self.host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.port = int(os.getenv('SMTP_PORT', '587'))
        self.username = os.getenv('SMTP_USERNAME', '')
        self.password = os.getenv('SMTP_PASSWORD', '')
        self.smtp_configured = bool(self.username and self.password)
        self.configured = self.use_resend or self.smtp_configured

        if self.use_resend:
            logger.info("使用 Resend API 發送 Email（HTTPS，不受 Railway SMTP 限制）")
        elif not self.smtp_configured:
            logger.info("SMTP 未設定（需要 SMTP_USERNAME + SMTP_PASSWORD 或 RESEND_API_KEY），Email 通知功能停用")

    def _is_configured(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        resend_api_key: str | None = None,
    ) -> bool:
        if (resend_api_key or '').strip():
            return True
        if self.use_resend:
            return True
        if smtp_username and smtp_password:
            return True
        return self.smtp_configured

    def send_async(
        self,
        to_email: str,
        subject: str,
        message: str,
        level: str = "info",
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        resend_api_key: str | None = None,
    ) -> None:
        if not self._is_configured(smtp_host, smtp_port, smtp_username, smtp_password, resend_api_key):
            return
        def _run():
            try:
                self._send(to_email, subject, message, level, smtp_host, smtp_port, smtp_username, smtp_password, resend_api_key)
            except Exception as e:
                logger.error(f"Email 發送失敗（{to_email}）：{e}")
        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def send_sync(
        self,
        to_email: str,
        subject: str,
        message: str,
        level: str = "info",
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        resend_api_key: str | None = None,
    ) -> None:
        """同步發送（供測試信等需等待結果的場景）。未設定時不拋錯，僅略過。"""
        if not self._is_configured(smtp_host, smtp_port, smtp_username, smtp_password, resend_api_key):
            return
        self._send(to_email, subject, message, level, smtp_host, smtp_port, smtp_username, smtp_password, resend_api_key)

    def _send(
        self,
        to_email: str,
        subject: str,
        message: str,
        level: str,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        resend_api_key: str | None = None,
    ) -> None:
        api_key = (resend_api_key or '').strip() or self.resend_api_key
        if api_key:
            self._send_via_resend(to_email, subject, message, level, api_key=api_key)
            return

        host = (smtp_host or self.host).strip()
        port = int(smtp_port) if smtp_port is not None else self.port
        username = (smtp_username or self.username).strip()
        password = smtp_password or self.password
        if not username or not password:
            return
        msg = MIMEMultipart('alternative')
        msg['From'] = f"NTUST Monitor <{username}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(self._build_html(message, level), 'html', 'utf-8'))

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)

        logger.info(f"Email 已發送至 {to_email}")

    def _send_via_resend(self, to_email: str, subject: str, message: str, level: str, api_key: str | None = None) -> None:
        """使用 Resend API 發送（HTTPS，不受 Railway SMTP 限制）。可傳入 api_key 作為使用者自有 Key。"""
        key = (api_key or '').strip() or self.resend_api_key
        if not key:
            return
        html = self._build_html(message, level)
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "from": self.resend_from,
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"Email 已發送至 {to_email}（Resend API）")

    @staticmethod
    def _build_html(message: str, level: str) -> str:
        palette = {
            'success': ('#059669', '#ecfdf5', '#d1fae5'),
            'error':   ('#dc2626', '#fef2f2', '#fecaca'),
            'warn':    ('#d97706', '#fffbeb', '#fde68a'),
            'info':    ('#2563eb', '#eff6ff', '#bfdbfe'),
        }
        color, bg, border_bg = palette.get(level, palette['info'])
        icon = {'success': '✅', 'error': '❌', 'warn': '⚠️'}.get(level, 'ℹ️')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return f"""\
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:0 auto;">
  <div style="background:linear-gradient(135deg,#1e3a8a,#3b82f6);padding:28px 24px;border-radius:16px 16px 0 0;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:22px;font-weight:700;letter-spacing:1px;">NTUST Monitor</h1>
    <p style="color:#bfdbfe;margin:6px 0 0;font-size:13px;">台科大課程缺額自動監聽系統</p>
  </div>
  <div style="background:#fff;padding:28px 24px;border:1px solid #e2e8f0;border-top:none;">
    <div style="background:{bg};border-left:4px solid {color};padding:16px 18px;border-radius:8px;margin-bottom:20px;">
      <p style="margin:0;font-size:15px;color:#1e293b;line-height:1.7;">
        <span style="font-size:18px;vertical-align:middle;margin-right:6px;">{icon}</span>
        {message}
      </p>
    </div>
    <p style="color:#94a3b8;font-size:11px;margin:0;">通知時間：{now}</p>
  </div>
  <div style="background:#f8fafc;padding:16px 24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 16px 16px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;margin:0;">此為自動通知信件，可至系統設定中關閉 Email 通知。</p>
  </div>
</div>"""
