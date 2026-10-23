import os

TOKEN = os.environ.get("DEMO_TOKEN")


def render(text, *, width=80):
    return text[:width]
