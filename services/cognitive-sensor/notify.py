"""
Daily Directive Notification
Shows a Windows toast notification with today's mode and action.
Requires: pip install plyer
"""

from pathlib import Path

BASE = Path(__file__).parent.resolve()
DIRECTIVE_PATH = BASE / "daily_directive.txt"


def get_directive():
    """Parse daily_directive.txt for mode and action."""
    if not DIRECTIVE_PATH.exists():
        return None, None

    text = DIRECTIVE_PATH.read_text(encoding="utf-8")
    mode = "UNKNOWN"
    action = ""

    for line in text.splitlines():
        if line.startswith("MODE:"):
            mode = line.split(":", 1)[1].strip()
        elif line.startswith("ACTION:"):
            action = line.split(":", 1)[1].strip()

    return mode, action


def notify():
    mode, action = get_directive()
    if not mode:
        return

    title = f"Pre Atlas — {mode}"
    message = action or f"Mode: {mode}"

    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Pre Atlas",
            timeout=10,
        )
    except ImportError:
        # Fallback: PowerShell toast (works on Windows without extra deps)
        import subprocess
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Pre Atlas").Show($toast)
        """
        try:
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=10
            )
        except Exception:
            # Silent fail — notification is best-effort
            pass


if __name__ == "__main__":
    notify()
