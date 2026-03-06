import requests
import re
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
from plyer import notification

from app.agents.report_ai import ReportAI
from app.agents.exporter import Exporter
from app.agents.chart_agent import ChartAgent
from app.agents.image_agent import ImageAgent
from app.agents.voice_reader import VoiceReader
from app.agents.chrome_agent import ChromeAgent
from app.agents.file_agent import FileAgent


class BrowserAgent:

    def __init__(self):
        self.base_dir = Path.home() / "Documents" / "Jarvis"
        self.reports_dir = self.base_dir / "Reports"

        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.ai = ReportAI()
        self.exporter = Exporter()
        self.chart = ChartAgent(self.base_dir)
        self.images = ImageAgent(self.base_dir)
        self.voice = VoiceReader()
        self.chrome = ChromeAgent()
        self.files = FileAgent()

    # -------------------------
    # SEARCH GOOGLE
    # -------------------------
    def search(self, query):

        url = f"https://www.google.com/search?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        links = []

        for a in soup.select("a"):
            href = a.get("href")
            if href and "http" in href:
                links.append(href)

        return links[:5]

    # -------------------------
    # EXTRACT TEXT
    # -------------------------
    def extract_text(self, url):

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")

            paragraphs = [p.get_text() for p in soup.find_all("p")]

            return " ".join(paragraphs)

        except:
            return ""

    # -------------------------
    # CREATE REPORT
    # -------------------------
    def create_report(self, topic, content):

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{topic}_{timestamp}"

        txt_path = self.reports_dir / f"{base_name}.txt"
        pdf_path = self.reports_dir / f"{base_name}.pdf"
        docx_path = self.reports_dir / f"{base_name}.docx"

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.exporter.export_pdf(content, pdf_path)
        self.exporter.export_docx(content, docx_path)

        return txt_path

    # -------------------------
    # NOTIFY
    # -------------------------
    def notify(self, message):

        notification.notify(
            title="Jarvis",
            message=message,
            timeout=5
        )

    # -------------------------
    # DETECT NUMBERS FOR CHART
    # -------------------------
    def extract_numbers(self, text):

        numbers = re.findall(r'\d+', text)
        return [int(n) for n in numbers[:10]]

    # -------------------------
    # MAIN RESEARCH
    # -------------------------
    def research(self, topic, length="1 page", read=False):

        links = self.search(topic)

        collected_text = ""
        sources = []

        for link in links:
            text = self.extract_text(link)
            if text:
                collected_text += text[:2000]
                sources.append(link)

        report_text = self.ai.generate(topic, collected_text, length)

        # citations
        citations = "\n\nSources:\n"
        for i, src in enumerate(sources, 1):
            citations += f"{i}. {src}\n"

        report_text += citations

        # charts
        nums = self.extract_numbers(report_text)
        if nums:
            self.chart.create_chart(nums, topic)

        # save report
        report_path = self.create_report(topic, report_text)

        self.notify(f"Report ready. Saved in {report_path}")

        # optional voice
        if read:
            self.voice.read_text(report_text[:1000])

        return report_path
