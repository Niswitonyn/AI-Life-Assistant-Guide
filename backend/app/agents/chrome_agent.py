import webbrowser

class ChromeAgent:

    def open(self, query=None, browser=None):

        url = "https://www.google.com"

        if query:
            url = f"https://www.google.com/search?q={query}"

        if browser == "chrome":
            webbrowser.get("chrome").open(url)

        elif browser == "firefox":
            webbrowser.get("firefox").open(url)

        elif browser == "edge":
            webbrowser.get("windows-default").open(url)

        else:
            # default browser
            webbrowser.open(url)
