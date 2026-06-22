=====================
Django REST Framework
=====================

.. versionadded:: 0.3.0

The classes in ``django_mongodb_extensions.rest_framework`` provide `Django
REST Framework <https://www.django-rest-framework.org/>`_ (DRF) serializer
support for :doc:`Django MongoDB Backend <django-mongodb-backend:index>` models.

All models using :class:`~django_mongodb_backend.fields.ObjectIdAutoField`
(the default primary key for MongoDB models) need
:class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer` rather
than DRF's ``ModelSerializer``, because the ``ObjectId`` primary key requires
special handling.

Installation
============

This package requires Django REST Framework 3.16 or later.

If you don't already have a compatible version of DRF installed, use the
``rest_framework`` extra to install it alongside this package:

.. code-block:: console

    $ pip install "django-mongodb-extensions[rest_framework]"

Then configure Django REST Framework by following its `installation
instructions <https://www.django-rest-framework.org/#installation>`_.

Usage
=====

``MongoModelSerializer``
------------------------

Use :class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer` for
regular Django models that contain MongoDB-specific fields::

    from django_mongodb_extensions.rest_framework import MongoModelSerializer


    class BookSerializer(MongoModelSerializer):
        class Meta:
            model = Book
            fields = "__all__"

``MongoModelSerializer`` extends DRF's ``ModelSerializer`` and automatically
generates the correct DRF fields for Django MongoDB Backend's fields:

* :class:`~django_mongodb_backend.fields.ArrayField`
* :class:`~django_mongodb_backend.fields.EmbeddedModelField`
* :class:`~django_mongodb_backend.fields.EmbeddedModelArrayField`
* :class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelField`
  (read-only)
* :class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelArrayField`
  (read-only)
* :class:`~django_mongodb_backend.fields.ObjectIdField`
* :class:`~django_mongodb_backend.fields.ObjectIdAutoField`

``EmbeddedModelSerializer``
---------------------------

Use :class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer`
for each :class:`~django_mongodb_backend.models.EmbeddedModel` you want to
serialize. Set ``Meta.model`` and ``Meta.fields`` just like other `DRF
serializers <https://www.django-rest-framework.org/api-guide/serializers/#specifying-which-fields-to-include>`_::

    from django_mongodb_extensions.rest_framework import EmbeddedModelSerializer


    class AddressSerializer(EmbeddedModelSerializer):
        class Meta:
            model = Address
            fields = "__all__"

Fields are auto-generated from the embedded model's field definitions,
supporting the same MongoDB-specific field types as
:class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer`. Unless
specified in ``Meta.fields`` the primary key field is excluded.

``to_internal_value()`` returns a model instance rather than a ``dict`` so
that the result integrates with the Django MongoDB Backend ORM layer.

Saving is not supported directly on ``EmbeddedModelSerializer`` — embedded
models must be saved through their parent model.

``EmbeddedModelSerializer`` extends
:class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer` and
supports the standard ``Meta`` options: ``fields``, ``exclude``,
``extra_kwargs``, and ``read_only_fields``.

Examples
========

Single embedded model field
----------------------------

In ``models.py``::

    from django.db import models
    from django_mongodb_backend.fields import EmbeddedModelField
    from django_mongodb_backend.models import EmbeddedModel


    class Address(EmbeddedModel):
        city = models.CharField(max_length=100)
        zip_code = models.CharField(max_length=20)


    class Person(models.Model):
        name = models.CharField(max_length=100)
        address = EmbeddedModelField(Address)

In ``serializers.py``::

    from django_mongodb_extensions.rest_framework import MongoModelSerializer

    from .models import Person


    class PersonSerializer(MongoModelSerializer):
        class Meta:
            model = Person
            fields = "__all__"

The ``address`` field is auto-generated as a nested
:class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer` for
``Address``. Serializing a ``Person`` instance::

    >>> person = Person.objects.get(name="Alice")
    >>> data = PersonSerializer(person).data
    {"id": "...", "name": "Alice", "address": {"city": "Berlin", "zip_code": "10115"}}

Deserializing and saving::

    serializer = PersonSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()

To customize the embedded model's serialization, declare an
:class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer`
subclass and assign it as an explicit field::

    from django_mongodb_extensions.rest_framework import (
        EmbeddedModelSerializer,
        MongoModelSerializer,
    )

    from .models import Address, Person


    class AddressSerializer(EmbeddedModelSerializer):
        class Meta:
            model = Address
            fields = "__all__"


    class PersonSerializer(MongoModelSerializer):
        address = AddressSerializer()

        class Meta:
            model = Person
            fields = "__all__"

Array of embedded models
------------------------

In ``models.py``::

    from django.db import models
    from django_mongodb_backend.fields import EmbeddedModelArrayField
    from django_mongodb_backend.models import EmbeddedModel


    class Tag(EmbeddedModel):
        label = models.CharField(max_length=50)


    class Article(models.Model):
        title = models.CharField(max_length=200)
        tags = EmbeddedModelArrayField(Tag, null=True)

In ``serializers.py``::

    from django_mongodb_extensions.rest_framework import MongoModelSerializer

    from .models import Article


    class ArticleSerializer(MongoModelSerializer):
        class Meta:
            model = Article
            fields = "__all__"

The ``tags`` field is auto-generated and represented as a JSON array of
objects:

.. code-block:: json

    {
      "id": "...",
      "title": "Hello",
      "tags": [{"label": "python"}, {"label": "mongodb"}]
    }

Polymorphic embedded model fields
----------------------------------

:class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelField` and
:class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelArrayField`
are serialized automatically by
:class:`~django_mongodb_extensions.rest_framework.PolymorphicEmbeddedModelSerializer`,
which dispatches to the correct concrete
:class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer`
based on the type of each instance:

In ``models.py``::

    from django.db import models
    from django_mongodb_backend.fields import PolymorphicEmbeddedModelField
    from django_mongodb_backend.models import EmbeddedModel


    class Dog(EmbeddedModel):
        name = models.CharField(max_length=100)
        barks = models.BooleanField(default=True)


    class Cat(EmbeddedModel):
        name = models.CharField(max_length=100)
        purrs = models.BooleanField(default=True)


    class PetOwner(models.Model):
        name = models.CharField(max_length=100)
        pet = PolymorphicEmbeddedModelField([Dog, Cat], null=True)

In ``serializers.py``::

    from django_mongodb_extensions.rest_framework import MongoModelSerializer

    from .models import PetOwner


    class PetOwnerSerializer(MongoModelSerializer):
        class Meta:
            model = PetOwner
            fields = "__all__"

Serializing a ``PetOwner`` with a ``Dog`` instance::

    >>> owner = PetOwner.objects.get(name="Alice")
    >>> data = PetOwnerSerializer(owner).data
    {"id": "...", "name": "Alice",
     "pet": {"_label": "myapp.Dog", "name": "Rex", "barks": true}}

The ``pet`` field is read-only. Write operations are not supported for
polymorphic embedded model fields.
