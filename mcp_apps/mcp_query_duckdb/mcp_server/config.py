from pathlib import Path
from typing import Optional

from pyhocon import ConfigFactory, ConfigTree


class AppConfig:

    config: Optional[ConfigTree] = None

    @classmethod
    def ensure_initialized(cls, conf_file: str = './mcp_server.conf'):
        if cls.config is None:
            config_file = Path(conf_file)

            cls.config = ConfigFactory.parse_file(
                config_file,
                resolve=True,
            )
