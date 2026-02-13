"""
Apollova Render Watcher — Notification Service
Desktop notifications (Windows toast / plyer). Falls back silently if unavailable.
"""

import sys
import logging

logger = logging.getLogger("apollova.notifications")


class NotificationService:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._backend = None

        if not enabled:
            return

        if sys.platform == "win32":
            try:
                from win10toast import ToastNotifier
                self._toaster = ToastNotifier()
                self._backend = "win10toast"
                return
            except ImportError:
                pass

        try:
            from plyer import notification as plyer_notify
            self._plyer = plyer_notify
            self._backend = "plyer"
        except ImportError:
            logger.debug("No notification backend available. Install win10toast or plyer.")

    def notify(self, title: str, message: str) -> None:
        if not self.enabled or not self._backend:
            return
        try:
            if self._backend == "win10toast":
                self._toaster.show_toast(title, message, duration=5, threaded=True)
            elif self._backend == "plyer":
                self._plyer.notify(title=title, message=message, app_name="Apollova", timeout=5)
        except Exception as e:
            logger.debug(f"Notification failed: {e}")

    def video_uploaded(self, filename: str, account: str, scheduled_at: str) -> None:
        self.notify("✅ Video Uploaded", f"{filename} → {account}\nScheduled: {scheduled_at}")

    def video_failed(self, filename: str, error: str) -> None:
        self.notify("❌ Upload Failed", f"{filename}: {error}")

    def auth_failed(self) -> None:
        self.notify("🔐 Auth Failed", "Could not authenticate with Apollova website")