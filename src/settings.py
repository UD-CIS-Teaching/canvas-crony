from __future__ import annotations
import yaml
from typing import TypedDict


class Settings(TypedDict):
    canvas_url: str
    canvas_token: str
    mail_server: str
    mail_server_port: int


def yaml_load(path):
    with open(path) as settings_file:
        return yaml.safe_load(settings_file)
