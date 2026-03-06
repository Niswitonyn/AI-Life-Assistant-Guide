import os
from pathlib import Path


class FileAgent:

    def find_file(self, name):

        home = Path.home()

        for root, dirs, files in os.walk(home):
            for f in files:
                if name.lower() in f.lower():
                    return os.path.join(root, f)

        return None

    def create_folder(self, folder_name: str, base: str = "documents"):
        folder_name = (folder_name or "").strip().strip("\"'")
        if not folder_name:
            return None

        base_map = {
            "documents": Path.home() / "Documents",
            "downloads": Path.home() / "Downloads",
            "desktop": Path.home() / "Desktop",
            "pictures": Path.home() / "Pictures",
        }
        parent = base_map.get(base.lower(), Path.home() / "Documents")
        target = parent / folder_name
        target.mkdir(parents=True, exist_ok=True)
        return str(target)
