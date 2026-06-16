=====================
Django REST Framework
=====================

.. versionadded:: 0.3.0

`Django REST Framework`_ (DRF) provides serializer support for
`Django MongoDB Backend`_ models through the classes in
``django_mongodb_extensions.rest_framework``.

All models using :class:`~django_mongodb_backend.fields.ObjectIdAutoField`
(the default primary key for MongoDB models) need
:class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer` rather
than DRF's ``ModelSerializer``, because the ObjectId primary key requires
special handling.

.. _Django REST Framework: https://www.django-rest-framework.org/
.. _Django MongoDB Backend: https://django-mongodb-backend.readthedocs.io/

Installation
============

This package requires Django REST Framework 3.14 or later.

If you don't already have a compatible version of DRF installed, use the
``rest_framework`` extra to install it alongside this package:

.. code-block:: console

   pip install "django-mongodb-extensions[rest_framework]"

Then configure Django REST Framework by following their
`installation instructions <https://www.django-rest-framework.org/#installation>`_.

Usage
=====

``EmbeddedModelSerializer``
---------------------------

Subclass :class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer` for each
:class:`~django_mongodb_backend.models.EmbeddedModel` you want to serialize.
Set ``Meta.model`` and ``Meta.fields`` just like Django's ``ModelForm``:

.. code-block:: python

   from django_mongodb_extensions.rest_framework import EmbeddedModelSerializer


   class AddressSerializer(EmbeddedModelSerializer):
       class Meta:
           model = Address
           fields = "__all__"

Fields are auto-generated from the embedded model's field definitions,
supporting the same MongoDB-specific field types as
:class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer`
(see below). The primary key field is excluded automatically.

``to_internal_value()`` returns an ``EmbeddedModel`` instance rather than a
plain ``dict``, so the result integrates directly with the Django MongoDB
Backend ORM layer.

Saving is not supported directly on ``EmbeddedModelSerializer`` — embedded
models must be saved through their parent model.

The following ``Meta`` options from DRF's ``ModelSerializer`` are **not**
supported:

* ``Meta.exclude`` — use an explicit field list instead.
* ``Meta.extra_kwargs`` — silently ignored; declare field overrides explicitly
  on the serializer class.
* ``Meta.read_only_fields`` — silently ignored for the same reason; use an
  explicit field declaration with ``read_only=True`` instead.

``MongoModelSerializer``
------------------------

Subclass :class:`~django_mongodb_extensions.rest_framework.MongoModelSerializer` for regular Django models that contain
MongoDB-specific fields:

.. code-block:: python

   from django_mongodb_extensions.rest_framework import MongoModelSerializer


   class BookSerializer(MongoModelSerializer):
       class Meta:
           model = Book
           fields = "__all__"

``MongoModelSerializer`` extends DRF's ``ModelSerializer`` and automatically
generates the correct DRF fields for:

* :class:`~django_mongodb_backend.fields.EmbeddedModelField`
* :class:`~django_mongodb_backend.fields.EmbeddedModelArrayField`
* :class:`~django_mongodb_backend.fields.ArrayField`
* :class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelField` (read-only)
* :class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelArrayField` (read-only)
* :class:`~django_mongodb_backend.fields.ObjectIdField`
* :class:`~django_mongodb_backend.fields.ObjectIdAutoField`

Explicit field declarations override the auto-generated ones:

.. code-block:: python

   class BookSerializer(MongoModelSerializer):
       author = AuthorSerializer()  # override the auto-generated field

       class Meta:
           model = Book
           fields = "__all__"

Examples
========

Single embedded model field
----------------------------

In ``models.py``:

.. code-block:: python

   from django.db import models
   from django_mongodb_backend.fields import EmbeddedModelField
   from django_mongodb_backend.models import EmbeddedModel


   class Address(EmbeddedModel):
       city = models.CharField(max_length=100)
       zip_code = models.CharField(max_length=20)


   class Person(models.Model):
       name = models.CharField(max_length=100)
       address = EmbeddedModelField(Address)

In ``serializers.py``:

.. code-block:: python

   from django_mongodb_extensions.rest_framework import (
       EmbeddedModelSerializer,
       MongoModelSerializer,
   )


   class AddressSerializer(EmbeddedModelSerializer):
       class Meta:
           model = Address
           fields = "__all__"


   class PersonSerializer(MongoModelSerializer):
       class Meta:
           model = Person
           fields = "__all__"

The ``address`` field on ``PersonSerializer`` is auto-generated as a nested
``EmbeddedModelSerializer`` for ``Address``. Declaring ``AddressSerializer``
explicitly is only needed when you want to customize the embedded model's
serialization::


   class PersonSerializer(MongoModelSerializer):
       address = AddressSerializer()  # override the auto-generated field

       class Meta:
           model = Person
           fields = "__all__"

Serializing a ``Person`` instance::

   person = Person.objects.get(pk=...)
   data = PersonSerializer(person).data
   # {"id": "...", "name": "Alice", "address": {"city": "Berlin", "zip_code": "10115"}}

Deserializing and saving::

   serializer = PersonSerializer(data=request.data)
   if serializer.is_valid():
       serializer.save()

Array of embedded models
------------------------

In ``models.py``::

   from django_mongodb_backend.fields import EmbeddedModelArrayField


   class Tag(EmbeddedModel):
       label = models.CharField(max_length=50)


   class Article(models.Model):
       title = models.CharField(max_length=200)
       tags = EmbeddedModelArrayField(Tag, null=True)

In ``serializers.py``::

   from django_mongodb_extensions.rest_framework import (
       EmbeddedModelSerializer,
       MongoModelSerializer,
   )


   class TagSerializer(EmbeddedModelSerializer):
       class Meta:
           model = Tag
           fields = "__all__"


   class ArticleSerializer(MongoModelSerializer):
       class Meta:
           model = Article
           fields = "__all__"

The ``tags`` field is represented as a JSON array of objects:

.. code-block:: json

   {"id": "...", "title": "Hello", "tags": [{"label": "python"}, {"label": "mongodb"}]}

Polymorphic embedded model fields
----------------------------------

:class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelField` and
:class:`~django_mongodb_backend.fields.PolymorphicEmbeddedModelArrayField`
are serialized automatically by
:class:`~django_mongodb_extensions.rest_framework.PolymorphicEmbeddedModelSerializer`,
which dispatches to the correct concrete
:class:`~django_mongodb_extensions.rest_framework.EmbeddedModelSerializer` based
on the type of each instance:

In ``models.py``::

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


   class PetOwnerSerializer(MongoModelSerializer):
       class Meta:
           model = PetOwner
           fields = "__all__"

Serializing a ``PetOwner`` with a ``Dog`` instance::

   owner = PetOwner.objects.get(pk=...)
   data = PetOwnerSerializer(owner).data
   # {"id": "...", "name": "Alice", "pet": {"name": "Rex", "barks": true}}

The ``pet`` and ``pets`` fields are read-only. Write operations are not
supported for polymorphic embedded model fields.
