from pathlib import Path
from urllib.parse import urlunparse

import attr
import keyring
import structlog
import toml
import xdg.BaseDirectory

logger = structlog.get_logger()

APP_NAME = "openconnect-sso"


def load():
    path = xdg.BaseDirectory.load_first_config(APP_NAME)
    if not path:
        return Config()
    config_path = Path(path) / "config.toml"
    if not config_path.exists():
        return Config()
    with config_path.open() as config_file:
        try:
            return Config.from_dict(toml.load(config_file))
        except Exception:
            logger.error(
                "Could not load configuration file, ignoring",
                path=config_path,
                exc_info=True,
            )
            return Config()


def save(config):
    path = xdg.BaseDirectory.save_config_path(APP_NAME)
    config_path = Path(path) / "config.toml"
    config_path.touch()

    with config_path.open("w") as config_file:
        try:
            toml.dump(config.as_dict(), config_file)
        except Exception:
            logger.error(
                "Could not save configuration file", path=config_path, exc_info=True
            )


@attr.s
class ConfigNode:
    @classmethod
    def from_dict(cls, d):
        if d is None:
            return None
        return cls(**d)

    def as_dict(self):
        return attr.asdict(self)


@attr.s
class HostProfile(ConfigNode):
    name = attr.ib(converter=str)
    address = attr.ib(converter=str)
    user_group = attr.ib(converter=str)

    @property
    def vpn_url(self):
        return urlunparse(("https", self.address, self.user_group, "", "", ""))


@attr.s
class AutoFillRule(ConfigNode):
    selector = attr.ib()
    fill = attr.ib(default=None)
    action = attr.ib(default=None)


def get_default_auto_fill_rules():
    return {
        "https://*": [
            AutoFillRule(selector="input[type=email]", fill="username").as_dict(),
            AutoFillRule(selector="input[type=password]", fill="password").as_dict(),
            AutoFillRule(selector="input[type=submit]", action="click").as_dict(),
        ]
    }


@attr.s
class Credentials(ConfigNode):
    username = attr.ib()

    @property
    def password(self):
        return keyring.get_credential(APP_NAME, self.username).password

    @password.setter
    def password(self, value):
        keyring.set_password(APP_NAME, self.username, value)


@attr.s
class Config(ConfigNode):
    default_profile = attr.ib(default=None, converter=HostProfile.from_dict)
    credentials = attr.ib(default=None, converter=Credentials.from_dict)
    auto_fill_rules = attr.ib(
        factory=get_default_auto_fill_rules,
        converter=lambda rules: {
            n: [AutoFillRule.from_dict(r) for r in rule] for n, rule in rules.items()
        },
    )
