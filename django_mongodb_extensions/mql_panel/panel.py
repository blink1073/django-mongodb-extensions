import uuid
from collections import defaultdict

from debug_toolbar.forms import SignedDataForm
from debug_toolbar.panels.sql.forms import SQLSelectForm
from debug_toolbar.panels.sql.panel import SQLPanel
from debug_toolbar.panels.sql.utils import contrasting_color_generator
from debug_toolbar.utils import render_stacktrace
from django.db import connections
from django.db.backends.signals import connection_created
from django.template.loader import render_to_string
from django.urls import path
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from . import views
from .utils import (
    get_mql_warning_threshold,
    patch_get_collection,
    patch_new_connection,
)

connection_created.connect(
    patch_new_connection,
    dispatch_uid="django_mongodb_extensions_mql_panel_patch_new_connection",
)


class MQLPanel(SQLPanel):
    nav_title = _("MQL")
    template = "mql_panel/mql.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mql_time = 0
        self._queries = []
        self._databases = {}

    @staticmethod
    def _hex_to_rgb(hex_color):
        """Convert a hex color string to RGB values.

        Used to convert hex colors from contrasting_color_generator() to RGB
        format for display in the debug toolbar UI.
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            # Return a default gray color if invalid
            return [128, 128, 128]
        try:
            # Convert hex to RGB
            return [int(hex_color[i : i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            return [128, 128, 128]

    @staticmethod
    def _is_read_operation(operation):
        return operation in {"aggregate"}

    @cached_property
    def content(self):
        stats = self.get_stats()
        colors = contrasting_color_generator()
        trace_colors = defaultdict(lambda: next(colors))
        for query in stats.get("queries", []):
            query["mql"] = query.get("mql", "")
            query["params"] = True
            query["form"] = SignedDataForm(
                auto_id=None,
                initial=SQLSelectForm(
                    initial={
                        "djdt_query_id": query["djdt_query_id"],
                        "request_id": self.toolbar.request_id,
                    }
                ).initial,
            )
            query["stacktrace"] = render_stacktrace(query["stacktrace"])
            query["trace_color"] = trace_colors[query["stacktrace"]]
        return render_to_string(self.template, stats)

    def disable_instrumentation(self):
        for connection in connections.all():
            if hasattr(connection, "_mql_djdt_logger"):
                connection._mql_djdt_logger = None

    def enable_instrumentation(self):
        # Only patch MongoDB connections (those with get_collection method).
        # This allows the panel to work in multi-database setups with
        # both MongoDB and relational databases.
        #
        # Use _mql_djdt_logger (not _djdt_logger) to avoid conflicting with the
        # SQL panel, which sets _djdt_logger on all connections regardless of type.
        for connection in connections.all():
            if hasattr(connection, "get_collection"):
                patch_get_collection(connection)
                connection._mql_djdt_logger = self

    def generate_stats(self, request, response):
        duplicate_query_groups = defaultdict(list)
        if self._queries:
            mql_warning_threshold = get_mql_warning_threshold()
            db_colors = contrasting_color_generator()
            for db in self._databases.values():
                hex_color = next(db_colors)
                db["rgb_color"] = self._hex_to_rgb(hex_color)
            width_ratio_tally = 0
            for query in self._queries:
                alias = query["alias"]
                dup_key = query.get("mql", "")
                duplicate_query_groups[(alias, dup_key)].append(query)
                query["is_slow"] = query["duration"] > mql_warning_threshold
                operation = query.get("mql_operation", "")
                # Only show Query/Explain buttons if it's a read operation and
                # the args were successfully serialized (mql_args_json is not
                # None).
                args_json = query.get("mql_args_json")
                query["is_query"] = (
                    self._is_read_operation(operation) and args_json is not None
                )
                query["rgb_color"] = self._databases[alias]["rgb_color"]
                try:
                    query["width_ratio"] = (query["duration"] / self._mql_time) * 100
                except ZeroDivisionError:
                    query["width_ratio"] = 0
                query["start_offset"] = width_ratio_tally
                query["end_offset"] = query["width_ratio"] + query["start_offset"]
                width_ratio_tally += query["width_ratio"]
        duplicate_colors = contrasting_color_generator()
        duplicate_counts = defaultdict(int)
        for (alias, _key), query_group in duplicate_query_groups.items():
            count = len(query_group)
            # Duplicates only apply when there are at least 2 identical queries.
            if count > 1:
                color = next(duplicate_colors)
                for query in query_group:
                    query["duplicate_count"] = count
                    query["duplicate_color"] = color
                duplicate_counts[alias] += count
        for alias, db_info in self._databases.items():
            db_info["duplicate_count"] = duplicate_counts[alias]
        self.record_stats(
            {
                "databases": sorted(
                    self._databases.items(), key=lambda x: -x[1]["time_spent"]
                ),
                "queries": self._queries,
                "mql_time": self._mql_time,
            }
        )

    def generate_server_timing(self, request, response):
        stats = self.get_stats()
        num_queries = len(stats.get("queries", []))
        title = f"MQL {num_queries} queries"
        value = stats.get("mql_time", 0)
        self.record_server_timing("mql_time", title, value)

    @classmethod
    def get_urls(cls):
        return [
            path("mql_query/", views.mql_query, name="mql_query"),
            path("mql_explain/", views.mql_explain, name="mql_explain"),
        ]

    @property
    def has_content(self):
        return bool(self._queries)

    @property
    def nav_subtitle(self):
        stats = self.get_stats()
        query_count = len(stats.get("queries", []))
        return ngettext(
            "%(query_count)d query in %(mql_time).3f ms",
            "%(query_count)d queries in %(mql_time).3f ms",
            query_count,
        ) % {
            "query_count": query_count,
            "mql_time": stats.get("mql_time"),
        }

    def record(self, **kwargs):
        kwargs["djdt_query_id"] = uuid.uuid4().hex
        self._queries.append(kwargs)
        alias = kwargs["alias"]
        if alias not in self._databases:
            self._databases[alias] = {
                "time_spent": kwargs["duration"],
                "num_queries": 1,
            }
        else:
            self._databases[alias]["time_spent"] += kwargs["duration"]
            self._databases[alias]["num_queries"] += 1
        self._mql_time += kwargs["duration"]

    @property
    def title(self):
        stats = self.get_stats()
        databases = stats.get("databases", {}) if stats else {}
        count = len(databases)
        return ngettext(
            "MQL queries from %(count)d connection",
            "MQL queries from %(count)d connections",
            count,
        ) % {"count": count}
