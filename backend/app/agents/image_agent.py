import requests
from pathlib import Path


class ImageAgent:

    def __init__(self, base_dir):
        self.img_dir = Path(base_dir) / "Images"
        self.img_dir.mkdir(parents=True, exist_ok=True)

    def download(self, urls, topic):

        for i, url in enumerate(urls):
            try:
                r = requests.get(url)
                path = self.img_dir / f"{topic}_{i}.jpg"

                with open(path, "wb") as f:
                    f.write(r.content)

            except:
                pass
