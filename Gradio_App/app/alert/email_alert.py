import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from app.alert.base import BaseAlertChannel
from app.utils.logger import logger
from config import Config

class EmailAlert(BaseAlertChannel):
    """
    SMTP Email Alert Channel Implementation.
    """

    def __init__(self):
        self.smtp_server = Config.SMTP_SERVER
        self.smtp_port = Config.SMTP_PORT
        self.smtp_user = Config.SMTP_USER
        self.smtp_pass = Config.SMTP_PASS
        self.receiver = Config.ALERT_RECEIVER_EMAIL

    def send_alert(self, alert_data: Dict[str, Any]) -> bool:
        if not self.smtp_user or not self.smtp_pass or not self.receiver:
            logger.warning("[EmailAlert] Missing SMTP credentials or receiver email. Skipping email sending.")
            return False

        subject = f"[ALERT] Negative Mention Detected - {alert_data.get('target_organization')}"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #d9534f;">🚨 SOCIAL LISTENING ALERT</h2>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Organization</td><td style="padding: 8px; border: 1px solid #ddd;">{alert_data.get('target_organization')}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Sentiment</td><td style="padding: 8px; border: 1px solid #ddd; color: red;">{alert_data.get('sentiment')}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Confidence</td><td style="padding: 8px; border: 1px solid #ddd;">{float(alert_data.get('confidence', 0.0)) * 100:.1f}%</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Source</td><td style="padding: 8px; border: 1px solid #ddd;">{alert_data.get('source')}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Content</td><td style="padding: 8px; border: 1px solid #ddd;"><i>{alert_data.get('text')}</i></td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Post URL</td><td style="padding: 8px; border: 1px solid #ddd;"><a href="{alert_data.get('post_url')}">{alert_data.get('post_url')}</a></td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Detected At</td><td style="padding: 8px; border: 1px solid #ddd;">{alert_data.get('detected_at')}</td></tr>
            </table>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = self.receiver
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logger.info(f"[EmailAlert] Email alert successfully sent to {self.receiver}")
            return True
        except Exception as e:
            logger.error(f"[EmailAlert] SMTP Email delivery error: {e}")
            return False
