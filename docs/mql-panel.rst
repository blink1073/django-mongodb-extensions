=========
MQL Panel
=========

The MQL Panel is a panel for
`Django Debug Toolbar <https://django-debug-toolbar.readthedocs.io/>`_
that provides insights into MongoDB queries executed during a request,
similar to how the SQL panel works for relational databases.

**Features:**

- View all MongoDB queries (MQL) executed during a request
- See query execution time and identify slow queries
- Re-execute read operations (aggregate) directly from the toolbar
- Explain query execution plans
- Color-coded query grouping for easy identification
- Detailed query statistics and performance metrics

Installation
============

First, install and configure Django Debug Toolbar by following their
`installation instructions <https://django-debug-toolbar.readthedocs.io/en/latest/installation.html>`_.

1. Add ``django_mongodb_extensions`` to ``INSTALLED_APPS``:

   .. code-block:: python

      INSTALLED_APPS = [
          # ...
          "django_mongodb_extensions",
          # ...
      ]

2. Add the MQL Panel to ``DEBUG_TOOLBAR_PANELS``:

   .. code-block:: python

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

Settings
========

.. setting:: DJDT_MQL_MAX_QUERY_RESULTS

``DJDT_MQL_MAX_QUERY_RESULTS``
------------------------------

Default: ``100``

Maximum number of documents to return when re-executing a query from the
toolbar.

.. setting:: DJDT_MQL_WARNING_THRESHOLD

``DJDT_MQL_WARNING_THRESHOLD``
-------------------------------

Default: ``500``

Queries slower than this threshold (in milliseconds) are highlighted in
the debug toolbar.
