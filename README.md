# django-mongodb-extensions

Extensions for Django MongoDB Backend

[![Documentation](https://readthedocs.org/projects/django-mongodb-extensions/badge/?version=latest)](https://django-mongodb-extensions.readthedocs.io/en/latest/)

## Version Support

| Django / Django MongoDB Backend | Django Debug Toolbar | Django REST Framework |
|---------------------------------|----------------------|-----------------------|
| 5.2                             | ≥5.1                 | ≥3.16                 |
| 6.0                             | ≥6.2                 | ≥3.17                 |

Django version support follows [Django's supported versions policy](https://www.djangoproject.com/download/#supported-versions).

## Installation

```bash
pip install django-mongodb-extensions
```

## Extensions

### MQL Panel

This panel for
[Django Debug Toolbar](https://github.com/jazzband/django-debug-toolbar)
provides insights into MongoDB queries executed during a request
similar to how the SQL panel works for relational databases.

**Features:**

- View all MongoDB queries (MQL) executed during a request
- See query execution time and identify slow queries
- Re-execute read operations (aggregate) directly from the toolbar
- Explain query execution plans
- Color-coded query grouping for easy identification
- Detailed query statistics and performance metrics

#### Configure the MQL Panel

First, install and configure Django Debug Toolbar by following their
[installation instructions](https://django-debug-toolbar.readthedocs.io/en/latest/installation.html).

1. **Add to `INSTALLED_APPS`** in your Django settings:

```python
INSTALLED_APPS = [
    # ...
    "django_mongodb_extensions",
    # ...
]
```

2. **Add the MQL Panel** to your debug toolbar configuration:

```python
DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.history.HistoryPanel",
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    # Add this:
    "django_mongodb_extensions.mql_panel.MQLPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]
```

3. **Optional:** Configure settings.

```python
# Maximum number of documents to return when re-executing select
# queries (default is 100).
DJDT_MQL_MAX_QUERY_RESULTS = 25

# Queries slower than this threshold (in milliseconds) are highlighted
# in the debug toolbar (default is 500 ms).
DJDT_MQL_WARNING_THRESHOLD = 1000
```

### Django REST Framework

Serializer support for Django MongoDB Backend models through
`django_mongodb_extensions.rest_framework`. See the
[documentation](https://django-mongodb-extensions.readthedocs.io/en/latest/rest-framework/)
for details.

## License

See [LICENSE](LICENSE) file for details.
