import os
import subprocess
import winreg
from pathlib import Path


class SystemAgent:

    # -------------------------
    # OPEN APPLICATION
    # -------------------------
    def open_app(self, app_name: str):

        app_name = app_name.lower()

        # 1️⃣ Try PATH execution
        try:
            subprocess.Popen(app_name)
            return f"Opening {app_name}"
        except Exception:
            pass

        # 2️⃣ Try Registry App Paths
        path = self._find_in_registry(app_name)
        if path:
            os.startfile(path)
            return f"Opening {app_name}"

        # 3️⃣ Try Start Menu shortcuts
        path = self._find_in_start_menu(app_name)
        if path:
            os.startfile(path)
            return f"Opening {app_name}"

        return None

    # -------------------------
    # REGISTRY SEARCH
    # -------------------------
    def _find_in_registry(self, app_name: str):

        reg_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        ]

        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)

                for i in range(0, winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)

                    if app_name in subkey_name.lower():

                        subkey = winreg.OpenKey(key, subkey_name)
                        value, _ = winreg.QueryValueEx(subkey, "")
                        return value

            except Exception:
                continue

        return None

    # -------------------------
    # START MENU SEARCH
    # -------------------------
    def _find_in_start_menu(self, app_name: str):

        start_paths = [
            Path(os.getenv("APPDATA")) / r"Microsoft\Windows\Start Menu\Programs",
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        ]

        for base in start_paths:
            for file in base.rglob("*"):
                if app_name in file.name.lower():
                    return str(file)

        return None

    # -------------------------
    # SYSTEM ACTIONS
    # -------------------------
    def system_action(self, text: str):

        cmd = text.lower()

        if "shutdown" in cmd:
            os.system("shutdown /s /t 1")
            return "Shutting down computer"

        if "restart" in cmd:
            os.system("shutdown /r /t 1")
            return "Restarting computer"

        if "lock" in cmd:
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "Locking computer"

        return None

    # -------------------------
    # OPEN FOLDER
    # -------------------------
    def open_folder(self, text: str):

        folders = {
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
            "desktop": Path.home() / "Desktop",
            "pictures": Path.home() / "Pictures",
        }

        for name, path in folders.items():
            if name in text:
                os.startfile(path)
                return f"Opening {name}"

        return None

    # -------------------------
    # MAIN EXECUTE
    # -------------------------
    def execute(self, text: str):

        text = text.lower()

        # open app
        if "open" in text:
            target = text.split("open", 1)[1].strip()

            folder_result = self.open_folder(target)
            if folder_result:
                return folder_result

            app_result = self.open_app(target)
            if app_result:
                return app_result

        # system action
        action = self.system_action(text)
        if action:
            return action

        return None
