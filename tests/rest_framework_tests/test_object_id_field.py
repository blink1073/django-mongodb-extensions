from bson import ObjectId
from django.test import SimpleTestCase
from rest_framework import serializers

from django_mongodb_extensions.rest_framework import ObjectIdField


class ObjectIdFieldToRepresentationTests(SimpleTestCase):
    def _field(self):
        f = ObjectIdField()
        f.field_name = "id"
        return f

    def test_objectid_serializes_as_string(self):
        oid = ObjectId()
        self.assertEqual(self._field().to_representation(oid), str(oid))

    def test_string_passthrough(self):
        s = "507f1f77bcf86cd799439011"
        self.assertEqual(self._field().to_representation(s), s)


class ObjectIdFieldToInternalValueTests(SimpleTestCase):
    invalid_msg = "Enter a valid ObjectId (24-character hex string)."

    def _field(self):
        f = ObjectIdField()
        f.field_name = "id"
        return f

    def test_valid_hex_string_accepted(self):
        s = str(ObjectId())
        self.assertEqual(self._field().to_internal_value(s), s)

    def test_invalid_string_rejected(self):
        with self.assertRaisesMessage(serializers.ValidationError, self.invalid_msg):
            self._field().to_internal_value("not-an-objectid")

    def test_too_short_rejected(self):
        with self.assertRaisesMessage(serializers.ValidationError, self.invalid_msg):
            self._field().to_internal_value("abc123")

    def test_empty_string_rejected(self):
        with self.assertRaisesMessage(serializers.ValidationError, self.invalid_msg):
            self._field().to_internal_value("")

    def test_integer_rejected(self):
        with self.assertRaisesMessage(serializers.ValidationError, self.invalid_msg):
            self._field().to_internal_value(42)
