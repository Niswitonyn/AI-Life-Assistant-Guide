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
