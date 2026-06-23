from django.test import SimpleTestCase, TestCase
from rest_framework import serializers

from django_mongodb_extensions.rest_framework import PolymorphicEmbeddedModelSerializer

from .models import Cat, Dog, PetOwner
from .serializers import PetOwnerSerializer


class PolymorphicEmbeddedModelSerializerReadOnlyTests(SimpleTestCase):
    msg = "PolymorphicEmbeddedModelSerializer is read-only."

    def test_to_internal_value_raises(self):
        s = PolymorphicEmbeddedModelSerializer()
        with self.assertRaisesMessage(NotImplementedError, self.msg):
            s.to_internal_value({})

    def test_create_raises(self):
        s = PolymorphicEmbeddedModelSerializer()
        with self.assertRaisesMessage(NotImplementedError, self.msg):
            s.create({})

    def test_update_raises(self):
        s = PolymorphicEmbeddedModelSerializer()
        with self.assertRaisesMessage(NotImplementedError, self.msg):
            s.update(None, {})


class PolymorphicEmbeddedModelSerializerTests(SimpleTestCase):
    def test_polymorphic_field_is_read_only(self):
        fields = PetOwnerSerializer().get_fields()
        self.assertTrue(fields["pet"].read_only)

    def test_polymorphic_array_field_is_read_only(self):
        fields = PetOwnerSerializer().get_fields()
        self.assertTrue(fields["pets"].read_only)

    def test_polymorphic_field_is_polymorphic_serializer(self):
        fields = PetOwnerSerializer().get_fields()
        self.assertIsInstance(fields["pet"], PolymorphicEmbeddedModelSerializer)

    def test_polymorphic_array_field_is_list_serializer(self):
        fields = PetOwnerSerializer().get_fields()
        self.assertIsInstance(fields["pets"], serializers.ListSerializer)
        self.assertIsInstance(fields["pets"].child, PolymorphicEmbeddedModelSerializer)


class PolymorphicEmbeddedModelSerializerReadTests(TestCase):
    def test_read_polymorphic_field_dog(self):
        original = PetOwner.objects.create(
            name="Alice", pet=Dog(name="Rex", barks=True), pets=None
        )
        loaded = PetOwner.objects.get(pk=original.pk)
        data = PetOwnerSerializer(loaded).data
        self.assertEqual(data["name"], "Alice")
        self.assertEqual(
            data["pet"],
            {"_label": "rest_framework_tests.Dog", "name": "Rex", "barks": True},
        )
        self.assertIsNone(data["pets"])

    def test_read_polymorphic_field_cat(self):
        original = PetOwner.objects.create(
            name="Bob", pet=Cat(name="Whiskers", purrs=False), pets=None
        )
        loaded = PetOwner.objects.get(pk=original.pk)
        data = PetOwnerSerializer(loaded).data
        self.assertEqual(
            data["pet"],
            {"_label": "rest_framework_tests.Cat", "name": "Whiskers", "purrs": False},
        )

    def test_read_polymorphic_array_field_mixed_types(self):
        original = PetOwner.objects.create(
            name="Carol",
            pet=None,
            pets=[Dog(name="Rex", barks=True), Cat(name="Luna", purrs=True)],
        )
        loaded = PetOwner.objects.get(pk=original.pk)
        data = PetOwnerSerializer(loaded).data
        self.assertIsNone(data["pet"])
        self.assertEqual(len(data["pets"]), 2)
        self.assertEqual(
            data["pets"][0],
            {"_label": "rest_framework_tests.Dog", "name": "Rex", "barks": True},
        )
        self.assertEqual(
            data["pets"][1],
            {"_label": "rest_framework_tests.Cat", "name": "Luna", "purrs": True},
        )

    def test_read_polymorphic_fields_null(self):
        original = PetOwner.objects.create(name="Dave", pet=None, pets=None)
        loaded = PetOwner.objects.get(pk=original.pk)
        data = PetOwnerSerializer(loaded).data
        self.assertIsNone(data["pet"])
        self.assertIsNone(data["pets"])
