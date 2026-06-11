import json
from typing import Any

from bson import json_util
from debug_toolbar.panels.sql.forms import SQLSelectForm
from debug_toolbar.toolbar import DebugToolbar
from django import forms
from django.core.exceptions import ValidationError
from django.db import connections
from django.utils.translation import gettext_lazy as _

from .utils import (
    get_max_query_results,
    parse_query_args,
)


class MQLBaseForm(SQLSelectForm):
    def _execute_operation(self, operation_type, executor_func):
        query_dict = self.cleaned_data["query"]
        alias = query_dict.get("alias", "default")
        connection = connections[alias]
        db = connection.database  # type: ignore[union-attr]
        collection_name, operation, args_list = parse_query_args(query_dict)
        collection = db[collection_name]
        return executor_func(
            db,
            collection,
            collection_name,
            operation,
            args_list,
        )

    def clean(self):
        from .panel import MQLPanel

        # Call forms.Form.clean() to bypass SQLSelectForm.clean() which has
        # SQL-specific validation
        cleaned_data: dict[str, Any] = forms.Form.clean(self)  # type: ignore[assignment]
        request_id = cleaned_data.get("request_id")
        if not request_id:
            raise ValidationError(_("Missing request ID."))
        djdt_query_id = cleaned_data.get("djdt_query_id")
        if not djdt_query_id:
            raise ValidationError(_("Missing query ID."))
        toolbar = DebugToolbar.fetch(request_id, panel_id=MQLPanel.panel_id)
        if toolbar is None:
            raise ValidationError(_("Data for this panel isn't available anymore."))
        panel = toolbar.get_panel_by_id(MQLPanel.panel_id)
        stats = panel.get_stats()
        if not stats or "queries" not in stats:
            raise ValidationError(_("Query data is not available."))
        # Find query in stats using djdt_query_id
        query = None
        for _query in stats["queries"]:
            if (
                isinstance(_query, dict)
                and _query.get("djdt_query_id") == djdt_query_id
            ):
                query = _query
                break
        if not query:
            raise ValidationError(_("Invalid query ID."))
        # Ensure query contains required keys
        if not all(key in query for key in ("alias", "mql")):
            raise ValidationError(_("Query data is incomplete."))
        cleaned_data["query"] = query
        return cleaned_data


class MQLExplainForm(MQLBaseForm):
    def _execute_aggregate(self, db, collection_name, args_list):
        pipeline = args_list[0] if args_list else []
        return db.command(
            "explain",
            {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}},
        )

    def _execute_explain(self, db, collection, collection_name, operation, args_list):
        if operation == "aggregate":
            explain_result = self._execute_aggregate(db, collection_name, args_list)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        explain_json = json_util.dumps(explain_result, indent=4)
        result = [[explain_json]]
        headers = ["MongoDB Explain Output (JSON)"]
        return result, headers

    def explain(self):
        return self._execute_operation("explain", self._execute_explain)


class MQLQueryForm(MQLBaseForm):
    def _execute_aggregate(self, collection, args_list):
        pipeline = args_list[0] if args_list else []
        result_docs = []
        max_results = get_max_query_results()
        with collection.aggregate(pipeline) as cursor:
            for i, doc in enumerate(cursor):
                if i >= max_results:
                    break
                result_docs.append(doc)
        return result_docs

    def _execute_query(self, db, collection, collection_name, operation, args_list):
        if operation == "aggregate":
            result_docs = self._execute_aggregate(collection, args_list)
        else:
            raise ValueError(f"Unsupported read operation: {operation}")
        return self.convert_documents_to_table(result_docs)

    def _flatten_single_key_dicts(self, obj):
        if isinstance(obj, dict):
            if len(obj) == 1 and next(iter(obj)).startswith("$"):
                only_value = next(iter(obj.values()))
                return self._flatten_single_key_dicts(only_value)
            return {
                key_name: self._flatten_single_key_dicts(value_item)
                for key_name, value_item in obj.items()
            }
        elif isinstance(obj, list):
            return [self._flatten_single_key_dicts(value_item) for value_item in obj]
        return obj

    def _format_cell_value(self, value):
        serialized = json_util.dumps(value)
        parsed_json = json.loads(serialized)
        flattened_value = self._flatten_single_key_dicts(parsed_json)
        if isinstance(flattened_value, (str, int, float, bool)):
            return {"value": str(flattened_value), "is_json": False}
        if isinstance(flattened_value, dict):
            return {
                "type": "dict",
                "value": self._format_dict_for_template(flattened_value),
                "is_json": False,
            }
        if isinstance(flattened_value, list):
            return {
                "type": "list",
                "value": self._format_list_for_template(flattened_value),
                "is_json": False,
            }
        return {
            "value": json.dumps(flattened_value, indent=4),
            "is_json": True,
        }

    def _format_dict_for_template(self, dictionary):
        return [
            {"key": key_name, **self._format_cell_value(value_item)}
            for key_name, value_item in dictionary.items()
        ]

    def _format_list_for_template(self, list_items):
        return [
            {"key": index, **self._format_cell_value(value_item)}
            for index, value_item in enumerate(list_items)
        ]

    def _format_row(self, row_dict):
        return [self._format_cell_value(cell_value) for cell_value in row_dict.values()]

    def convert_documents_to_table(self, documents):
        if not documents:
            return [], []
        # Collect all unique field names
        all_fields = set()
        for doc in documents:
            all_fields.update(doc.keys())
        # Sort fields for consistent column ordering, with _id first if present
        headers = sorted(all_fields)
        if "_id" in headers:
            headers.remove("_id")
            headers.insert(0, "_id")
        # Convert each document to a row with formatted values
        rows = []
        for doc in documents:
            row = [self._format_cell_value(doc.get(field)) for field in headers]
            rows.append(row)
        return rows, headers

    def query(self):
        return self._execute_operation("query", self._execute_query)
