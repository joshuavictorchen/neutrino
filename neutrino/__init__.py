from neutrino.main import Neutrino
from neutrino import authenticator, datum, link, stream, tools

import os
from pathlib import Path

root_dir = Path(
    os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
)

db_path = root_dir / "database"

settings = tools.parse_yaml(
    root_dir / "strings/neutrino-settings.yaml", echo_yaml=False
)

api_response_keys = settings.get("api_response_keys")
