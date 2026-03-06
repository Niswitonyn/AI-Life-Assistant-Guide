from plyer import notification


class DesktopNotifier:

    @staticmethod
    def send(title: str, message: str):
        notification.notify(
            title=title,
            message=message,
            timeout=10
        )
