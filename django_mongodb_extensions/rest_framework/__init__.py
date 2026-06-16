try:
    from .fields import ObjectIdField
    from .serializers import (
        EmbeddedModelSerializer,
        MongoModelSerializer,
        PolymorphicEmbeddedModelSerializer,
    )
except ModuleNotFoundError as exc:
    if exc.name == "rest_framework":
        raise ModuleNotFoundError(
            "djangorestframework is required to use django_mongodb_extensions.rest_framework. "
            "Install it with: pip install 'django-mongodb-extensions[rest_framework]'"
        ) from None
    raise

__all__ = [
    "EmbeddedModelSerializer",
    "MongoModelSerializer",
    "ObjectIdField",
    "PolymorphicEmbeddedModelSerializer",
]
