import unittest

try:
    import rest_framework  # noqa: F401
except ImportError:
    raise unittest.SkipTest("djangorestframework not installed") from None

from django.core.exceptions import FieldDoesNotExist
from django.test import SimpleTestCase
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from django_mongodb_extensions.rest_framework import (
    EmbeddedModelSerializer,
)

from .models import City, CityWithUniqueCode, Country
from .serializers import CitySerializer, CountrySerializer, StatusTagSerializer


class EmbeddedModelSerializerToRepresentationTests(SimpleTestCase):
    def test_basic(self):
        city = City(name="Paris", population=2_000_000)
        data = CitySerializer(city).data
        self.assertEqual(data, {"name": "Paris", "population": 2_000_000})

    def test_nested_embedded_field(self):
        capital = City(name="Berlin", population=3_500_000)
        country = Country(name="Germany", capital=capital, cities=None, languages=None)
        data = CountrySerializer(country).data
        self.assertEqual(
            data,
            {
                "name": "Germany",
                "capital": {"name": "Berlin", "population": 3_500_000},
                "cities": None,
                "languages": None,
            },
        )

    def test_nested_embedded_array_field(self):
        cities = [
            City(name="Lyon", population=500_000),
            City(name="Nice", population=340_000),
        ]
        country = Country(
            name="France", capital=None, cities=cities, languages=["French"]
        )
        data = CountrySerializer(country).data
        self.assertEqual(
            data,
            {
                "name": "France",
                "capital": None,
                "cities": [
                    {"name": "Lyon", "population": 500_000},
                    {"name": "Nice", "population": 340_000},
                ],
                "languages": ["French"],
            },
        )

    def test_null_embedded_field(self):
        country = Country(name="Iceland", capital=None, cities=None, languages=None)
        data = CountrySerializer(country).data
        self.assertIsNone(data["capital"])

    def test_array_field(self):
        country = Country(
            name="Belgium", capital=None, cities=None, languages=["French", "Dutch"]
        )
        data = CountrySerializer(country).data
        self.assertEqual(data["languages"], ["French", "Dutch"])


class EmbeddedModelSerializerToInternalValueTests(SimpleTestCase):
    def test_basic(self):
        s = CitySerializer(data={"name": "Tokyo", "population": 13_000_000})
        self.assertTrue(s.is_valid(), s.errors)
        result = s.validated_data
        self.assertIsInstance(result, City)
        self.assertEqual(result.name, "Tokyo")
        self.assertEqual(result.population, 13_000_000)

    def test_nested_embedded_field(self):
        data = {
            "name": "Japan",
            "capital": {"name": "Tokyo", "population": 13_000_000},
            "cities": None,
            "languages": None,
        }
        s = CountrySerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        result = s.validated_data
        self.assertIsInstance(result, Country)
        self.assertIsInstance(result.capital, City)
        self.assertEqual(result.capital.name, "Tokyo")

    def test_nested_embedded_array_field(self):
        data = {
            "name": "France",
            "capital": None,
            "cities": [
                {"name": "Lyon", "population": 500_000},
                {"name": "Nice", "population": 340_000},
            ],
            "languages": None,
        }
        s = CountrySerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        result = s.validated_data
        self.assertIsInstance(result, Country)
        self.assertIsInstance(result.cities[0], City)
        self.assertEqual(result.cities[0].name, "Lyon")

    def test_array_field(self):
        data = {
            "name": "Switzerland",
            "capital": None,
            "cities": None,
            "languages": ["French", "German", "Italian"],
        }
        s = CountrySerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data.languages, ["French", "German", "Italian"])

    def test_null_fields(self):
        data = {"name": "Empty", "capital": None, "cities": None, "languages": None}
        s = CountrySerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        result = s.validated_data
        self.assertIsNone(result.capital)
        self.assertIsNone(result.cities)

    def test_choices_field(self):
        s = StatusTagSerializer(data={"label": "Test", "status": 1})
        self.assertTrue(s.is_valid(), s.errors)
        result = s.validated_data
        self.assertEqual(result.label, "Test")
        self.assertEqual(result.status, 1)


class EmbeddedModelSerializerMetaTests(SimpleTestCase):
    def test_explicit_fields(self):
        class CityNameOnlySerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["name"]

        data = CityNameOnlySerializer(City(name="Berlin", population=3_500_000)).data
        self.assertEqual(data, {"name": "Berlin"})
        self.assertNotIn("population", data)

    def test_primary_key_excluded_from_all(self):
        fields = CitySerializer().get_fields()
        self.assertNotIn("id", fields)

    def test_primary_key_explicit_raises(self):
        class BadSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["id", "name"]

        s = BadSerializer()
        with self.assertRaises(ValueError):
            s.get_fields()

    def test_missing_model_raises(self):
        class NoModelSerializer(EmbeddedModelSerializer):
            class Meta:
                fields = "__all__"

        with self.assertRaises(AssertionError):
            NoModelSerializer().get_fields()

    def test_missing_fields_raises(self):
        class NoFieldsSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City

        with self.assertRaises(AssertionError):
            NoFieldsSerializer().get_fields()

    def test_unknown_field_raises(self):
        class BadFieldsSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["nonexistent"]

        with self.assertRaises(FieldDoesNotExist):
            BadFieldsSerializer().get_fields()

    def test_invalid_fields_type_raises(self):
        class BadFieldsTypeSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = "name"

        with self.assertRaises(AssertionError):
            BadFieldsTypeSerializer().get_fields()

    def test_declared_field_overrides_auto(self):
        class CustomCitySerializer(EmbeddedModelSerializer):
            name = serializers.IntegerField()

            class Meta:
                model = City
                fields = "__all__"

        fields = CustomCitySerializer().get_fields()
        self.assertIsInstance(fields["name"], serializers.IntegerField)

    def test_unique_validator_stripped(self):
        class CityWithUniqueCodeSerializer(EmbeddedModelSerializer):
            class Meta:
                model = CityWithUniqueCode
                fields = "__all__"

        fields = CityWithUniqueCodeSerializer().get_fields()
        code_field = fields["code"]
        for v in code_field.validators:
            self.assertNotIsInstance(v, UniqueValidator)
