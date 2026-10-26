"""Solo instancia desechable local de revisión; nunca usa credenciales de producción."""
from .test_settings import *  # noqa: F403

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "127.0.0.1",
    "PORT": "55440",
    "USER": "ap_test",
    "OPTIONS": {"connect_timeout": 5},
    "NAME": "postgres",
    "TEST": {"NAME": "test_fortex_ap_review"},
}}
