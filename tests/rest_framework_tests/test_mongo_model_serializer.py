from django.db import models
from django.test import SimpleTestCase, TestCase
from rest_framework import serializers

from django_mongodb_extensions.rest_framework import MongoModelSerializer, ObjectIdField

from .models import City, Continent, Country, Dog, PetOwner, Widget
from .serializers import CitySerializer, ContinentSerializer


class MongoModelSerializerToRepresentationTests(SimpleTestCase):
    def _make_continent(self):
        capital = City(name="Amsterdam", population=900_000)
        country = Country(
            name="Netherlands",
            capital=capital,
            cities=[City(name="Rotterdam", population=650_000)],
            languages=["Dutch"],
        )
        return Continent(
            name="Europe",
            country=country,
            countries=[country],
            notable_cities=["Amsterdam"],
        )

    def test_embedded_field(self):
        continent = self._make_continent()
        data = ContinentSerializer(continent).data
        self.assertEqual(data["country"]["name"], "Netherlands")
        self.assertEqual(data["country"]["capital"]["name"], "Amsterdam")

    def test_embedded_array_field(self):
        continent = self._make_continent()
        data = ContinentSerializer(continent).data
        self.assertEqual(len(data["countries"]), 1)
        self.assertEqual(data["countries"][0]["name"], "Netherlands")

    def test_array_field(self):
        continent = self._make_continent()
        data = ContinentSerializer(continent).data
        self.assertEqual(data["notable_cities"], ["Amsterdam"])

    def test_null_values(self):
        continent = Continent(
            name="Antarctica", country=None, countries=None, notable_cities=None
        )
        data = ContinentSerializer(continent).data
        self.assertIsNone(data["country"])
        self.assertIsNone(data["countries"])
        self.assertIsNone(data["notable_cities"])


class MongoModelSerializerToInternalValueTests(SimpleTestCase):
    def test_embedded_field(self):
        data = {
            "name": "Oceania",
            "country": {
                "name": "Australia",
                "capital": {"name": "Canberra", "population": 450_000},
                "cities": None,
                "languages": ["English"],
            },
            "countries": None,
            "notable_cities": None,
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        validated = s.validated_data
        self.assertIsInstance(validated["country"], Country)
        self.assertIsInstance(validated["country"].capital, City)
        self.assertEqual(validated["country"].capital.name, "Canberra")

    def test_embedded_array_field(self):
        data = {
            "name": "Africa",
            "country": None,
            "countries": [
                {
                    "name": "Nigeria",
                    "capital": {"name": "Abuja", "population": 3_600_000},
                    "cities": None,
                    "languages": ["English"],
                }
            ],
            "notable_cities": None,
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        validated = s.validated_data
        self.assertIsInstance(validated["countries"][0], Country)

    def test_null_embedded_field(self):
        data = {
            "name": "Atlantis",
            "country": None,
            "countries": None,
            "notable_cities": None,
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIsNone(s.validated_data["country"])

    def test_array_field(self):
        data = {
            "name": "Asia",
            "country": None,
            "countries": None,
            "notable_cities": ["Tokyo", "Beijing"],
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["notable_cities"], ["Tokyo", "Beijing"])


class MongoModelSerializerExplicitFieldTests(SimpleTestCase):
    def test_explicit_embedded_field(self):
        class CustomContinentSerializer(MongoModelSerializer):
            country = CitySerializer()

            class Meta:
                model = Continent
                fields = ["name", "country"]

        fields = CustomContinentSerializer().get_fields()
        self.assertIsInstance(fields["country"], CitySerializer)

    def test_partial(self):
        class PartialContinentSerializer(MongoModelSerializer):
            class Meta:
                model = Continent
                fields = ["name"]

        fields = PartialContinentSerializer().get_fields()
        self.assertEqual(list(fields), ["name"])


class FieldMappingPropagationTests(SimpleTestCase):
    def _make_custom_serializer(self):
        class CustomContinentSerializer(MongoModelSerializer):
            serializer_field_mapping = {
                **MongoModelSerializer.serializer_field_mapping,
                models.IntegerField: serializers.FloatField,
            }

            class Meta:
                model = Continent
                fields = "__all__"

        return CustomContinentSerializer

    def test_custom_mapping_applies_to_direct_embedded_field(self):
        cls = self._make_custom_serializer()
        country_serializer = cls().get_fields()["country"]
        city_serializer = country_serializer.get_fields()["capital"]
        self.assertIsInstance(
            city_serializer.get_fields()["population"], serializers.FloatField
        )

    def test_custom_mapping_applies_to_embedded_array_field(self):
        cls = self._make_custom_serializer()
        country_serializer = cls().get_fields()["country"]
        cities_list_serializer = country_serializer.get_fields()["cities"]
        city_fields = cities_list_serializer.child.get_fields()
        self.assertIsInstance(city_fields["population"], serializers.FloatField)

    def test_default_mapping_unchanged_for_base_serializer(self):
        base_fields = ContinentSerializer().get_fields()
        capital_fields = base_fields["country"].get_fields()["capital"].get_fields()
        self.assertIsInstance(capital_fields["population"], serializers.IntegerField)

    def test_custom_mapping_applies_to_polymorphic_field(self):
        class CustomPetOwnerSerializer(MongoModelSerializer):
            serializer_field_mapping = {
                **MongoModelSerializer.serializer_field_mapping,
                models.BooleanField: serializers.CharField,
            }

            class Meta:
                model = PetOwner
                fields = ["pet"]

        pet_field = CustomPetOwnerSerializer().get_fields()["pet"]
        dog = Dog(name="Rex", barks=True)
        data = pet_field.to_representation(dog)
        # With BooleanField → CharField mapping, barks is serialized as a string.
        self.assertIsInstance(data["barks"], str)


class ObjectIdFieldMappingTests(SimpleTestCase):
    def test_object_id_auto_field_maps_to_object_id_field(self):
        class WidgetSerializer(MongoModelSerializer):
            class Meta:
                model = Widget
                fields = "__all__"

        fields = WidgetSerializer().get_fields()
        self.assertIsInstance(fields["id"], ObjectIdField)
        # ObjectIdField subclasses CharField.
        self.assertIsInstance(fields["id"], serializers.CharField)

    def test_object_id_field_maps_to_object_id_field(self):
        class WidgetSerializer(MongoModelSerializer):
            class Meta:
                model = Widget
                fields = "__all__"

        fields = WidgetSerializer().get_fields()
        self.assertIsInstance(fields["ref"], ObjectIdField)


class MongoModelSerializerCreateTests(TestCase):
    def test_create_with_embedded_field(self):
        data = {
            "name": "Europe",
            "country": {
                "name": "Germany",
                "capital": {"name": "Berlin", "population": 3_500_000},
                "cities": None,
                "languages": None,
            },
            "countries": None,
            "notable_cities": None,
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        continent = s.save()

        loaded = Continent.objects.get(pk=continent.pk)
        self.assertEqual(loaded.name, "Europe")
        self.assertIsInstance(loaded.country, Country)
        self.assertEqual(loaded.country.name, "Germany")
        self.assertIsInstance(loaded.country.capital, City)
        self.assertEqual(loaded.country.capital.name, "Berlin")

    def test_create_with_embedded_array_field(self):
        data = {
            "name": "South America",
            "country": None,
            "countries": [
                {
                    "name": "Brazil",
                    "capital": {"name": "Brasília", "population": 3_000_000},
                    "cities": None,
                    "languages": ["Portuguese"],
                },
                {
                    "name": "Argentina",
                    "capital": {"name": "Buenos Aires", "population": 3_100_000},
                    "cities": None,
                    "languages": ["Spanish"],
                },
            ],
            "notable_cities": None,
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        continent = s.save()

        loaded = Continent.objects.get(pk=continent.pk)
        self.assertEqual(len(loaded.countries), 2)
        self.assertIsInstance(loaded.countries[0], Country)
        self.assertEqual(loaded.countries[0].name, "Brazil")
        self.assertEqual(loaded.countries[1].name, "Argentina")

    def test_create_with_array_field(self):
        data = {
            "name": "Asia",
            "country": None,
            "countries": None,
            "notable_cities": ["Tokyo", "Beijing", "Mumbai"],
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        continent = s.save()

        loaded = Continent.objects.get(pk=continent.pk)
        self.assertEqual(loaded.notable_cities, ["Tokyo", "Beijing", "Mumbai"])

    def test_create_with_null_fields(self):
        data = {
            "name": "Antarctica",
            "country": None,
            "countries": None,
            "notable_cities": None,
        }
        s = ContinentSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        continent = s.save()

        loaded = Continent.objects.get(pk=continent.pk)
        self.assertIsNone(loaded.country)
        self.assertIsNone(loaded.countries)
        self.assertIsNone(loaded.notable_cities)


class MongoModelSerializerUpdateTests(TestCase):
    def test_update_with_embedded_field(self):
        continent = Continent.objects.create(
            name="Europe",
            country=Country(name="France", capital=None, cities=None, languages=None),
            countries=None,
            notable_cities=None,
        )
        data = {
            "name": "Europe",
            "country": {
                "name": "Germany",
                "capital": {"name": "Berlin", "population": 3_500_000},
                "cities": None,
                "languages": None,
            },
            "countries": None,
            "notable_cities": None,
        }
        s = ContinentSerializer(continent, data=data)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        loaded = Continent.objects.get(pk=continent.pk)
        self.assertEqual(loaded.name, "Europe")
        self.assertEqual(loaded.country.name, "Germany")
        self.assertIsInstance(loaded.country.capital, City)
        self.assertEqual(loaded.country.capital.name, "Berlin")

    def test_update_with_array_field(self):
        continent = Continent.objects.create(
            name="Asia",
            country=None,
            countries=None,
            notable_cities=["Tokyo"],
        )
        data = {
            "name": "Asia",
            "country": None,
            "countries": None,
            "notable_cities": ["Tokyo", "Beijing"],
        }
        s = ContinentSerializer(continent, data=data)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        loaded = Continent.objects.get(pk=continent.pk)
        self.assertEqual(loaded.notable_cities, ["Tokyo", "Beijing"])
