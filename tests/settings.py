import os


def always_show_toolbar(request):
    return True


SECRET_KEY = "test-secret-key-for-django-mongodb-extensions"
DEBUG = True
INSTALLED_APPS = [
    "tests.apps.MongoAuthConfig",
    "tests.apps.MongoContentTypesConfig",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "debug_toolbar",
    "rest_framework",
    "django_mongodb_extensions",
    "tests.rest_framework_tests",
]
DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "NAME": "django_mongodb_extensions",
        "HOST": os.environ.get("MONGODB_URI", "mongodb://localhost:27017/"),
    }
}
DATABASE_ROUTERS = ["django_mongodb_backend.routers.MongoRouter"]
MIDDLEWARE = []
# Use a callback that doesn't check DEBUG, since tests run with DEBUG=False.
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": always_show_toolbar,
}
ROOT_URLCONF = "tests.urls"
USE_TZ = True
STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"
# Disable migrations for tests
MIGRATION_MODULES = {
    "auth": None,
    "contenttypes": None,
    "sessions": None,
    "rest_framework_tests": None,
}
# Include MQLPanel for testing
DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.history.HistoryPanel",
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    "django_mongodb_extensions.mql_panel.MQLPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.alerts.AlertsPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]
