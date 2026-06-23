from bson import ObjectId
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from rest_framework import serializers

from django_mongodb_extensions.rest_framework import (
    EmbeddedModelSerializer,
    MongoModelSerializer,
)

from .models import City, Country, Event, Widget
from .serializers import CitySerializer, CountrySerializer, StatusTagSerializer


class EmbeddedModelSerializerToRepresentationTests(SimpleTestCase):
    def test_embedded_model_field(self):
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
            "name": "Italy",
            "capital": None,
            "cities": [
                {"name": "Rome", "population": 2_800_000},
                {"name": "Milan", "population": 1_300_000},
            ],
            "languages": ["Italian"],
        }
        s = CountrySerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        result = s.validated_data
        self.assertIsInstance(result, Country)
        self.assertEqual(len(result.cities), 2)
        self.assertIsInstance(result.cities[0], City)
        self.assertEqual(result.cities[0].name, "Rome")

    def test_missing_required_field_raises(self):
        s = CitySerializer(data={"name": "NoPopulation"})
        self.assertFalse(s.is_valid())
        self.assertEqual(s.errors["population"], ["This field is required."])

    def test_wrong_type_raises(self):
        s = CitySerializer(data={"name": "BadPop", "population": "not-a-number"})
        self.assertFalse(s.is_valid())
        self.assertEqual(s.errors["population"], ["A valid integer is required."])

    def test_null_embedded_field_accepted(self):
        data = {"name": "Nowhere", "capital": None, "cities": None, "languages": None}
        s = CountrySerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data.capital)

    def test_invalid_nested_embedded_field_errors(self):
        data = {
            "name": "Badland",
            "capital": {"name": "Oops", "population": "not-a-number"},
            "cities": None,
            "languages": None,
        }
        s = CountrySerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertEqual(
            s.errors["capital"]["population"], ["A valid integer is required."]
        )

    def test_invalid_nested_embedded_array_field_errors(self):
        data = {
            "name": "Badland",
            "capital": None,
            "cities": [
                {"name": "Good", "population": 1_000_000},
                {"name": "Bad", "population": "not-a-number"},
            ],
            "languages": None,
        }
        s = CountrySerializer(data=data)
        self.assertFalse(s.is_valid())
        # Errors are indexed by position; the first city is valid.
        self.assertEqual(
            s.errors["cities"][1]["population"], ["A valid integer is required."]
        )


class EmbeddedModelSerializerNotSavableTests(SimpleTestCase):
    def test_create_raises(self):
        s = CitySerializer()
        msg = "EmbeddedModel instances cannot be saved independently."
        with self.assertRaisesMessage(NotImplementedError, msg):
            s.create({})

    def test_update_raises(self):
        s = CitySerializer()
        msg = "EmbeddedModel instances cannot be updated independently."
        with self.assertRaisesMessage(NotImplementedError, msg):
            s.update(City(), {})


class EmbeddedModelSerializerMetaValidationTests(SimpleTestCase):
    def test_missing_meta_model_raises(self):
        class BrokenSerializer(EmbeddedModelSerializer):
            class Meta:
                fields = "__all__"

        self.assertRaisesMessage(
            AssertionError,
            'Class BrokenSerializer missing "Meta.model" attribute',
            BrokenSerializer().get_fields,
        )

    def test_missing_meta_fields_raises(self):
        class BrokenSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City

        self.assertRaisesMessage(
            AssertionError,
            "fields' attribute or the 'exclude' attribute",
            BrokenSerializer().get_fields,
        )

    def test_unknown_field_name_raises(self):
        class BrokenSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["name", "nonexistent_field"]

        self.assertRaisesMessage(
            ImproperlyConfigured,
            "Field name `nonexistent_field` is not valid for model `City`",
            BrokenSerializer().get_fields,
        )

    def test_explicit_primary_key_included(self):
        class CityWithIdSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["id", "name"]

        fields = CityWithIdSerializer().get_fields()
        self.assertEqual(list(fields), ["id", "name"])

    def test_explicit_primary_key_serializes_none_when_unset(self):
        class CityWithIdSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["id", "name"]

        city = City(name="Paris", population=2_000_000)
        data = CityWithIdSerializer(city).data
        # Embedded model instances have no pk value unless explicitly set.
        self.assertIsNone(data["id"])
        self.assertEqual(data["name"], "Paris")

    def test_explicit_primary_key_serializes_when_set(self):
        class CityWithIdSerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = ["id", "name"]

        city = City(
            id=ObjectId("000000000000000000000042"),
            name="Berlin",
            population=3_500_000,
        )
        data = CityWithIdSerializer(city).data
        # ObjectIdAutoField maps to ObjectIdField (CharField subclass), coerced
        # to str.
        self.assertEqual(data["id"], "000000000000000000000042")
        self.assertEqual(data["name"], "Berlin")


class ChoicesCoercionTests(SimpleTestCase):
    def test_choices_field_becomes_choice_field(self):
        fields = StatusTagSerializer().get_fields()
        self.assertIsInstance(fields["status"], serializers.ChoiceField)

    def test_choices_field_rejects_invalid_value(self):
        s = StatusTagSerializer(data={"label": "test", "status": 99})
        self.assertFalse(s.is_valid())
        self.assertEqual(s.errors["status"], ['"99" is not a valid choice.'])

    def test_choices_field_accepts_valid_value(self):
        s = StatusTagSerializer(data={"label": "active", "status": 1})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data.status, 1)

    def test_choices_field_on_mongo_serializer(self):
        # MongoModelSerializer must propagate choices coercion into
        # auto-generated EmbeddedModelSerializer instances for nested fields.
        class EventSerializer(MongoModelSerializer):
            class Meta:
                model = Event
                fields = ["tag"]

        tag_fields = EventSerializer().get_fields()["tag"].get_fields()
        self.assertIsInstance(tag_fields["status"], serializers.ChoiceField)
        self.assertEqual(
            dict(tag_fields["status"].choices), {1: "Active", 2: "Inactive"}
        )

    def test_choices_field_in_array_field(self):
        # An ArrayField whose base_field has choices must produce a ListField
        # with a ChoiceField child.
        class WidgetSerializer(MongoModelSerializer):
            class Meta:
                model = Widget
                fields = ["statuses"]

        statuses_field = WidgetSerializer().get_fields()["statuses"]
        self.assertIsInstance(statuses_field, serializers.ListField)
        self.assertIsInstance(statuses_field.child, serializers.ChoiceField)


class DeclaredFieldOverrideTests(SimpleTestCase):
    def test_declared_field_overrides_auto_generated(self):
        class CityWithFloatPop(EmbeddedModelSerializer):
            population = serializers.FloatField()

            class Meta:
                model = City
                fields = "__all__"

        fields = CityWithFloatPop().get_fields()
        self.assertIsInstance(fields["population"], serializers.FloatField)

    def test_declared_field_is_used_in_serialization(self):
        class CityUpperName(EmbeddedModelSerializer):
            name = serializers.SerializerMethodField()

            def get_name(self, obj):
                return obj.name.upper()

            class Meta:
                model = City
                fields = "__all__"

        city = City(name="paris", population=2_000_000)
        data = CityUpperName(city).data
        self.assertEqual(data["name"], "PARIS")

    def test_declared_field_used_in_deserialization(self):
        class CityWithFloatPop(EmbeddedModelSerializer):
            population = serializers.FloatField()

            class Meta:
                model = City
                fields = "__all__"

        s = CityWithFloatPop(data={"name": "Berlin", "population": "1.5e6"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsInstance(s.validated_data.population, float)


class MetaOptionsTests(SimpleTestCase):
    def test_exclude(self):
        class CitySerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                exclude = ["population"]

        fields = CitySerializer().get_fields()
        self.assertIn("name", fields)
        self.assertNotIn("population", fields)

    def test_extra_kwargs(self):
        class CitySerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = "__all__"
                extra_kwargs = {"name": {"required": False}}

        s = CitySerializer(data={"population": 1_000_000})
        self.assertTrue(s.is_valid(), s.errors)

    def test_read_only_fields(self):
        class CitySerializer(EmbeddedModelSerializer):
            class Meta:
                model = City
                fields = "__all__"
                read_only_fields = ["name"]

        fields = CitySerializer().get_fields()
        self.assertTrue(fields["name"].read_only)
