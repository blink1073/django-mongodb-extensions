from __future__ import annotations

import copy
import functools
from typing import Any

from django.core.exceptions import FieldDoesNotExist
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
from rest_framework.fields import CharField, ChoiceField, Field
from rest_framework.serializers import ALL_FIELDS, ModelField
from rest_framework.utils.field_mapping import ClassLookupDict, get_field_kwargs
from rest_framework.validators import UniqueValidator

from .fields import ObjectIdField as ObjectIdSerializerField

# Single source of truth for the MongoDB-extended field mapping.
# EmbeddedModelSerializer uses this via _FIELD_MAPPING; MongoModelSerializer
# inherits it directly as serializer_field_mapping, keeping both in sync.
_MONGO_FIELD_MAPPING: dict[type, type] = {
    **serializers.ModelSerializer.serializer_field_mapping,
    ObjectIdAutoField: ObjectIdSerializerField,
    ObjectIdField: ObjectIdSerializerField,
}

# ClassLookupDict wrapper used by _get_serializer_field
# (EmbeddedModelSerializer path).
_FIELD_MAPPING: ClassLookupDict = ClassLookupDict(_MONGO_FIELD_MAPPING)


def _make_embedded_serializer(
    embedded_model: type[Any],
    field_mapping: ClassLookupDict | None = None,
) -> type[EmbeddedModelSerializer]:
    attrs: dict[str, Any] = {
        "Meta": type("Meta", (), {"model": embedded_model, "fields": ALL_FIELDS}),
    }
    if field_mapping is not None:
        attrs["_field_mapping"] = field_mapping
    return type(
        f"{embedded_model.__name__}Serializer",
        (EmbeddedModelSerializer,),
        attrs,
    )


# Intentionally module-scoped: auto-generated serializer classes are
# stateless and safe to reuse across requests. The cache is never cleared,
# which is acceptable because concrete polymorphic types are fixed at import
# time and do not change at runtime.
@functools.cache
def _cached_polymorphic_serializer(
    embedded_model: type[Any],
) -> type[EmbeddedModelSerializer]:
    return _make_embedded_serializer(embedded_model)


def _build_embedded_field(
    model_field: models.Field[Any, Any],
    field_mapping: ClassLookupDict | None = None,
) -> tuple[type[Any], dict[str, Any]] | None:
    """
    Return (field_class, kwargs) for MongoDB-specific fields, or None for
    standard fields.
    """
    # PolymorphicEmbeddedModelArrayField before ArrayField — subclass check
    # must come first.
    if isinstance(model_field, PolymorphicEmbeddedModelArrayField):
        kwargs: dict[str, Any] = {"many": True, "read_only": True}
        if model_field.null:
            kwargs["allow_null"] = True
        return PolymorphicEmbeddedModelSerializer, kwargs

    if isinstance(model_field, PolymorphicEmbeddedModelField):
        kwargs = {"read_only": True}
        if model_field.null:
            kwargs["allow_null"] = True
        return PolymorphicEmbeddedModelSerializer, kwargs

    # EmbeddedModelArrayField before ArrayField — subclass check must come
    # first.
    if isinstance(model_field, EmbeddedModelArrayField):
        child_cls = _make_embedded_serializer(model_field.embedded_model, field_mapping)
        kwargs = {"many": True}
        if model_field.null:
            kwargs["allow_null"] = True
        return child_cls, kwargs

    if isinstance(model_field, EmbeddedModelField):
        field_cls = _make_embedded_serializer(model_field.embedded_model, field_mapping)
        kwargs = {}
        if model_field.null:
            kwargs["allow_null"] = True
        return field_cls, kwargs

    if isinstance(model_field, ArrayField):
        child_field = _get_serializer_field(model_field.base_field, field_mapping)
        kwargs = {}
        if model_field.null:
            kwargs["allow_null"] = True
        if child_field:
            kwargs["child"] = child_field
        return serializers.ListField, kwargs

    return None


def _get_serializer_field(
    model_field: models.Field[Any, Any],
    field_mapping: ClassLookupDict | None = None,
) -> Field[Any, Any, Any, Any] | None:
    """Return a DRF field instance for model_field, or None to skip it."""
    result = _build_embedded_field(model_field, field_mapping)
    if result:
        field_cls, kwargs = result
        return field_cls(**kwargs)

    mapping = field_mapping if field_mapping is not None else _FIELD_MAPPING
    try:
        field_class: type[Field[Any, Any, Any, Any]] = mapping[model_field]
    except KeyError:
        return None
    field_kwargs: dict[str, Any] = get_field_kwargs(model_field.name, model_field)
    # Coerce any field with choices to ChoiceField (mirrors DRF's
    # build_standard_field).
    if field_kwargs.get("choices"):
        field_class = serializers.ChoiceField
    # model_field is only valid for DRF's ModelField fallback; strip it for
    # all others.
    if not issubclass(field_class, ModelField):
        field_kwargs.pop("model_field", None)
    # allow_blank is only valid for CharField and ChoiceField.
    if not issubclass(field_class, (CharField, ChoiceField)):
        field_kwargs.pop("allow_blank", None)
    # EmbeddedModels cannot be queried; UniqueValidator would crash at
    # is_valid() time.
    if "validators" in field_kwargs:
        field_kwargs["validators"] = [
            v for v in field_kwargs["validators"] if not isinstance(v, UniqueValidator)
        ]
    return field_class(**field_kwargs)


class PolymorphicEmbeddedModelSerializer(serializers.BaseSerializer):
    """
    Read-only serializer for
    :class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelField`
    values.

    Serializes each instance using an auto-generated
    :class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer`
    for its concrete type. A ``_label`` key (e.g. ``"myapp.Dog"``) is
    included in the output so consumers can identify the concrete type.
    Write operations are not supported because
    ``PolymorphicEmbeddedModelField`` is not editable.
    """

    def to_representation(self, instance: Any) -> Any:
        if instance is None:
            return None
        concrete_type: type = type(instance)
        meta = concrete_type._meta
        data = _cached_polymorphic_serializer(concrete_type)(
            instance, context=self.context
        ).data
        return {"_label": f"{meta.app_label}.{meta.object_name}", **data}

    def to_internal_value(self, data: Any) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} is read-only.")

    def create(self, validated_data: Any) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} is read-only.")

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} is read-only.")


class EmbeddedModelSerializer(serializers.Serializer):
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

    class Meta:
        model: type[Any]
        fields: list[str] | str

    def get_fields(self) -> dict[str, Field[Any, Any, Any, Any]]:
        assert hasattr(
            self, "Meta"
        ), f"Class {self.__class__.__name__} missing 'Meta' attribute."
        meta = type(self).Meta
        assert hasattr(
            meta, "model"
        ), f"Class {self.__class__.__name__}.Meta missing 'model' attribute."
        assert hasattr(
            meta, "fields"
        ), f"Class {self.__class__.__name__}.Meta missing 'fields' attribute."

        model: type[Any] = meta.model
        all_fields_names = {f.name: f for f in model._meta.fields}

        has_explicit_fields = meta.fields != ALL_FIELDS
        field_names: list[str] | str = meta.fields
        if field_names == ALL_FIELDS:
            field_names = list(all_fields_names)
        elif not isinstance(field_names, (list, tuple)):
            raise AssertionError(
                f"{self.__class__.__name__}.Meta.fields must be '__all__' or a list/tuple."
            )

        # Explicitly declared fields take priority over auto-generated ones.
        # Deepcopy mirrors DRF's own get_fields(): field instances are mutated
        # when bound (bind() sets field_name and parent), so each serializer
        # instance needs its own copy to avoid cross-instance interference.
        declared_fields = copy.deepcopy(self._declared_fields)
        # A custom mapping may be set by _make_embedded_serializer on
        # auto-generated classes.
        field_mapping: ClassLookupDict | None = getattr(
            type(self), "_field_mapping", None
        )

        result: dict[str, Field[Any, Any, Any, Any]] = {}
        for name in field_names:
            if name in declared_fields:
                result[name] = declared_fields[name]
                continue
            model_field = all_fields_names.get(name)
            if model_field is None:
                raise FieldDoesNotExist(
                    f"Field '{name}' not found on {model.__name__}."
                )
            # Skip the primary key when using __all__; otherwise, it can be
            # included in a fields list.
            if not has_explicit_fields and model_field.primary_key:
                continue
            drf_field = _get_serializer_field(model_field, field_mapping)
            if drf_field:
                result[name] = drf_field
        return result

    def to_internal_value(self, data: Any) -> Any:
        validated: dict[str, Any] = super().to_internal_value(data)
        meta = type(self).Meta
        return meta.model(**validated)

    def create(self, validated_data: Any) -> Any:
        raise NotImplementedError(
            "EmbeddedModel instances cannot be saved independently."
        )

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError(
            "EmbeddedModel instances cannot be updated independently."
        )


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

    def build_field(
        self,
        field_name: str,
        info: Any,
        model_class: type[models.Model],
        nested_depth: int,
    ) -> tuple[type[Any], dict[str, Any]]:
        try:
            model_field = model_class._meta.get_field(field_name)
        except FieldDoesNotExist:
            return super().build_field(field_name, info, model_class, nested_depth)

        if not isinstance(model_field, models.Field):
            return super().build_field(field_name, info, model_class, nested_depth)

        result = _build_embedded_field(
            model_field,
            ClassLookupDict(self.serializer_field_mapping),  # type: ignore[arg-type]
        )
        if result:
            return result

        return super().build_field(field_name, info, model_class, nested_depth)
