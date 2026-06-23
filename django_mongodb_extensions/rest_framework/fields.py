from __future__ import annotations

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import serializers


class ObjectIdField(serializers.CharField):
    default_error_messages = {
        **serializers.CharField.default_error_messages,
        "invalid": "Enter a valid ObjectId (24-character hex string).",
    }

    def to_representation(self, value: Any) -> str:
        return str(value)

    def to_internal_value(self, data: Any) -> str:
        # Return str (not ObjectId) so the value is JSON-serializable and
        # compatible with DRF's string-based field contract. Django MongoDB
        # Backend accepts str values for ObjectId fields.
        value: str = super().to_internal_value(data)
        try:
            ObjectId(value)
        except (InvalidId, TypeError):
            self.fail("invalid")
        return value
