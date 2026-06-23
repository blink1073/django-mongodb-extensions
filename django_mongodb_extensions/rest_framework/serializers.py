from __future__ import annotations

import functools
from typing import Any

from django.db import models
from django_mongodb_backend.fields import (
    ArrayField,
    EmbeddedModelArrayField,
    EmbeddedModelField,
    ObjectIdAutoField,
    ObjectIdField,
    PolymorphicEmbeddedModelArrayField,
    PolymorphicEmbeddedModelField,
)
from rest_framework import serializers
from rest_framework.serializers import ALL_FIELDS

from .fields import ObjectIdField as ObjectIdSerializerField

_MONGO_FIELD_MAPPING: dict[type, type] = {
    **serializers.ModelSerializer.serializer_field_mapping,
    ObjectIdAutoField: ObjectIdSerializerField,
    ObjectIdField: ObjectIdSerializerField,
}


class MongoModelSerializer(serializers.ModelSerializer):
    """
    ``ModelSerializer`` with automatic support for MongoDB-specific fields.

    ``EmbeddedModelField``, ``EmbeddedModelArrayField``, ``ArrayField``,
    ``PolymorphicEmbeddedModelField``, and
    ``PolymorphicEmbeddedModelArrayField``
    are detected automatically::

        class BookSerializer(MongoModelSerializer):
            class Meta:
                model = Book
                fields = '__all__'

    Explicit field declarations override the auto-generated fields::

        class BookSerializer(MongoModelSerializer):
            author = AuthorSerializer()

            class Meta:
                model = Book
                fields = '__all__'
    """

    serializer_field_mapping = _MONGO_FIELD_MAPPING

    def build_standard_field(
        self,
        field_name: str,
        model_field: models.Field[Any, Any],
    ) -> tuple[type[Any], dict[str, Any]]:
        kwargs: dict[str, Any]
        field_mapping_items = frozenset(self.serializer_field_mapping.items())
        poly_cls = _make_polymorphic_serializer(field_mapping_items)
        # PolymorphicEmbeddedModelArrayField before ArrayField — subclass check
        # must come first.
        if isinstance(model_field, PolymorphicEmbeddedModelArrayField):
            kwargs = {"many": True, "read_only": True}
            if model_field.null:
                kwargs["allow_null"] = True
            return poly_cls, kwargs

        if isinstance(model_field, PolymorphicEmbeddedModelField):
            kwargs = {"read_only": True}
            if model_field.null:
                kwargs["allow_null"] = True
            return poly_cls, kwargs

        # EmbeddedModelArrayField before ArrayField — subclass check must come
        # first.
        if isinstance(model_field, EmbeddedModelArrayField):
            child_cls = _make_embedded_serializer(
                model_field.embedded_model,
                frozenset(self.serializer_field_mapping.items()),
            )
            kwargs = {"many": True}
            if model_field.null:
                kwargs["allow_null"] = True
            return child_cls, kwargs

        if isinstance(model_field, EmbeddedModelField):
            field_cls = _make_embedded_serializer(
                model_field.embedded_model,
                frozenset(self.serializer_field_mapping.items()),
            )
            kwargs = {}
            if model_field.null:
                kwargs["allow_null"] = True
            return field_cls, kwargs

        if isinstance(model_field, ArrayField):
            child_class, child_kwargs = self.build_standard_field(
                "child", model_field.base_field
            )
            kwargs = {}
            if model_field.null:
                kwargs["allow_null"] = True
            kwargs["child"] = child_class(**child_kwargs)
            return serializers.ListField, kwargs

        return super().build_standard_field(field_name, model_field)


class EmbeddedModelSerializer(MongoModelSerializer):
    """
    Serializer for EmbeddedModel instances.

    Subclass and set ``Meta.model`` and ``Meta.fields``::

        class AddressSerializer(EmbeddedModelSerializer):
            class Meta:
                model = Address
                fields = '__all__'

    ``EmbeddedModelSerializer`` auto-generates DRF fields from the embedded
    model's field definitions, including nested ``EmbeddedModelField`` and
    ``EmbeddedModelArrayField``. Explicitly declared fields on a subclass
    take priority over auto-generated ones.
    """

    def get_field_names(
        self,
        declared_fields: Any,
        info: Any,
    ) -> list[str]:
        field_names = super().get_field_names(declared_fields, info)
        # ModelSerializer includes the pk by default; exclude it when the
        # caller used '__all__' since embedded models have no meaningful pk.
        if getattr(self.Meta, "fields", None) == ALL_FIELDS:
            pk_name = self.Meta.model._meta.pk.name
            field_names = [f for f in field_names if f != pk_name]
        return field_names

    def get_uniqueness_extra_kwargs(
        self,
        field_names: Any,
        declared_fields: Any,
        extra_kwargs: Any,
    ) -> tuple[Any, dict[str, Any]]:
        # EmbeddedModels have no collection of their own; skip uniqueness
        # validators that would try to query the database.
        return extra_kwargs, {}

    def to_internal_value(self, data: Any) -> Any:
        validated: dict[str, Any] = super().to_internal_value(data)
        return type(self).Meta.model(**validated)

    def create(self, validated_data: Any) -> Any:
        raise NotImplementedError(
            "EmbeddedModel instances cannot be saved independently."
        )

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError(
            "EmbeddedModel instances cannot be updated independently."
        )


class PolymorphicEmbeddedModelSerializer(serializers.BaseSerializer):
    """
    Read-only serializer for
    :class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelField`
    values.

    Serialize each instance using an auto-generated
    :class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer`
    for its concrete type. A ``_label`` key (e.g. ``"myapp.Dog"``) is
    included in the output so consumers can identify the concrete type.
    Write operations are not supported because
    ``PolymorphicEmbeddedModelField`` is not editable.
    """

    # Set by _make_polymorphic_serializer to propagate a custom
    # serializer_field_mapping from the parent MongoModelSerializer into the
    # auto-generated concrete-type EmbeddedModelSerializers.
    _field_mapping_items: frozenset[tuple[type, type]] | None = None

    def to_representation(self, instance: Any) -> Any:
        if instance is None:
            return None
        concrete_type: type = type(instance)
        meta = concrete_type._meta
        data = _make_embedded_serializer(
            concrete_type, type(self)._field_mapping_items
        )(instance, context=self.context).data
        return {"_label": f"{meta.app_label}.{meta.object_name}", **data}

    def to_internal_value(self, data: Any) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} is read-only.")

    def create(self, validated_data: Any) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} is read-only.")

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} is read-only.")


# Auto-generated serializer classes are stateless and safe to reuse across
# requests. The cache is module-scoped and never cleared, which is acceptable
# because both embedded model types and serializer_field_mapping dicts are
# fixed at class-definition time and do not change at runtime.
@functools.cache
def _make_embedded_serializer(
    embedded_model: type[Any],
    field_mapping_items: frozenset[tuple[type, type]] | None = None,
) -> type[EmbeddedModelSerializer]:
    attrs: dict[str, Any] = {
        "Meta": type("Meta", (), {"model": embedded_model, "fields": ALL_FIELDS}),
    }
    if field_mapping_items is not None:
        attrs["serializer_field_mapping"] = dict(field_mapping_items)
    return type(
        f"{embedded_model.__name__}Serializer",
        (EmbeddedModelSerializer,),
        attrs,
    )


@functools.cache
def _make_polymorphic_serializer(
    field_mapping_items: frozenset[tuple[type, type]],
) -> type[PolymorphicEmbeddedModelSerializer]:
    return type(
        "PolymorphicEmbeddedModelSerializer",
        (PolymorphicEmbeddedModelSerializer,),
        {"_field_mapping_items": field_mapping_items},
    )
