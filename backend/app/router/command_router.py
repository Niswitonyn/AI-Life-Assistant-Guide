class CommandRouter:

    def __init__(self, system_agent=None, browser_agent=None, file_agent=None):
        self.system = system_agent
        self.browser = browser_agent
        self.files = file_agent

    # -------------------------
    # OLD RULE-BASED ROUTER (optional)
    # -------------------------
    def route(self, text: str):

        text_lower = text.lower()

        # SYSTEM
        if "shutdown" in text_lower:
            return self.system.execute("shutdown")

        if "lock" in text_lower:
            return self.system.execute("lock")

        if "open chrome" in text_lower or "open browser" in text_lower:
            return self.system.execute("open chrome")

        # RESEARCH
        if "research" in text_lower or "search" in text_lower:

            topic = text
            length = "1 page"

            if "2 page" in text_lower:
                length = "2 pages"

            if "paragraph" in text_lower:
                length = "1 paragraph"

            read = "read" in text_lower

            return self.browser.research(topic, length=length, read=read)

        # FILE
        if "find file" in text_lower or "search file" in text_lower:
            words = text.split()
            name = words[-1]
            return self.files.find_file(name)

        return None

    # -------------------------
    # SMART ROUTER EXECUTION (AI DATA)
    # -------------------------
    def execute(self, data: dict):

        intent = data.get("intent")

        # SYSTEM
        if intent == "system":
            app = data.get("app")
            if app:
                return self.system.execute(f"open {app}")

        # RESEARCH
        if intent == "research":
            topic = data.get("topic")
            length = data.get("length", "1 page")
            read = data.get("read", False)

            return self.browser.research(topic, length, read)

        # FILE
        if intent == "file":
            name = data.get("filename")
            if name:
                return self.files.find_file(name)

        return None
