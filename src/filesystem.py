import re


def clean_filename(dirty: str) -> str:
    return re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F]", "-", dirty)
