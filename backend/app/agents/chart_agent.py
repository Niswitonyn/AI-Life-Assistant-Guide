import matplotlib.pyplot as plt
from pathlib import Path


class ChartAgent:

    def __init__(self, base_dir):
        self.chart_dir = Path(base_dir) / "Charts"
        self.chart_dir.mkdir(parents=True, exist_ok=True)

    def create_chart(self, numbers, title):

        plt.figure()
        plt.plot(numbers)
        plt.title(title)

        path = self.chart_dir / f"{title}.png"
        plt.savefig(path)
        plt.close()
