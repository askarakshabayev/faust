.. _changelog:

==============================
 Changes
==============================

This document contain change notes for bugfix releases in
the Faust 1.10 series. If you're looking for previous releases,
please visit the :ref:`history` section.

.. _version-1.10.0:

1.10.0
======
:release-date: TBA
:release-by: Ask Solem (:github_user:`ask`)

- **Requirements**

    + Now depends on :pypi:`robinhood-aiokafka` 1.1.3

    + Now depends on :ref:`Mode 4.1.8 <mode:version-4.1.8>`.


.. _v1_10-news:

News
----

- Agents: ``use_reply_headers`` is now enabled by default (Issue #469).

    This affects users of ``Agent.ask``, ``.cast``, ``.map``, ``.kvmap``,
    and ``.join`` only.

    This requires a Kafka broker with headers support. If you want
    to avoid making this change you can disable it manually
    by passing the ``use_reply_headers`` argument to the agent decorator:

    .. sourcecode:: python

        @app.agent(use_reply_headers=False)

- Models: Support fields with arbitrarily nested type expressions.

    This extends model fields to support arbitrarily nested type
    expressions, such as ``List[Dict[str, List[Set[MyModel]]]``

- Models: Support for fields that have named tuples.

    This includes named tuples with fields that are also models.

    For example:

    .. sourcecode:: python

        from typing import NamedTuple
        from faust import Record

        class Point(Record):
            x: int
            y: int

        class NamedPoint(NamedTuple):
            name: str
            point: Point

        class Arena(Record):
            points: List[NamedPoint]

    Note that this does not currently support ``collections.namedtuple``.

- Models: Support for fields that are unions of models,
    such as ``Union[ModelX, ModelY]``.

- Models: Optimizations and backward incompatible changes.

    + Serialization is now 4x faster.
    + Deserialization is 2x faster.

    Related fields are now lazily loaded, so models and complex structures
    are only loaded as needed.

    One important change is that serializing a model will
    no longer traverse the structure for child models, instead we rely
    on the json serializer to call `Model.__json__()` during serializing.

    Specifically this means, where previously having models

    .. sourcecode:: python

        class X(Model):
            name: str

        class Y(Model):
            x: X

    and calling ``Y(X('foo')).to_representation()`` it would return:

    .. sourcecode:: pycon

        >>> Y(X('foo')).to_representation()
        {
            'x': {
                'name': 'foo',
                '__faust': {'ns': 'myapp.X'},
            },
            '__faust': {'ns': 'myapp.Y'},
        }

    after this change it will instead return the objects as-is:

    .. sourcecode:: pycon

        >>> Y(X('foo')).to_representation()
        {
            'x': X(name='foo'),
            '__faust': {'ns': 'myapp.Y'},
        }

    This is a backward incompatible change for anything that relies
    on the previous behavior, but in most apps will be fine as the
    Faust json serializer will automatically handle models and call
    ``Model.__json__()`` on them as needed.

    **Removed attributes**

    The following attributes have been removed from ``Model._options``,
    and :class:`~faust.types.FieldDescriptorT`, as they are no longer needed,
    or no longer make sense when supporting arbitrarily nested structures.

    *:class:`Model._options <faust.types.models.ModelOptions>`*

    - ``.models``

        Previously map of fields that have related models.
        This index is no longer used, and a field can have multiple
        related models now.  You can generate this index using the
        statement:

        .. sourcecode:: python

            {field: field.related_models
                for field in model._options.descriptors
                if field.related_models}

    - ``.modelattrs``

    - ``.field_coerce``

    - ``.initfield``

    - ``.polyindex``

    *:class:`~faust.types.FieldDescriptorT`*

    - ``generic_type``
    - ``member_type``

- Tables: Fixed behavior of global tables.

    Contributed by DhruvaPatil98 (:github_user:`DhruvaPatil98`).

- Tables: Added ability to iterate through all keys in a global table.

    Contributed by DhruvaPatil98 (:github_user:`DhruvaPatil98`).

- Tables: Attempting to call ``keys()``/``items()``/``values()`` on
  a windowset now raises an exception.

    This change was added to avoid unexpected behavior.

    Contributed by Sergej Herbert (:github_user:`fr-ser`).

- Models: Added new bool field type :class:`~faust.models.fields.BooleanField`.

    Thanks to John Heinnickel.

- aiokafka: Now raises an exception when topic name length exceeds 249
  characters (Issue #411).

- New :setting:`broker_api_version` setting.

    The new setting acts as default for both the new
    :setting:`consumer_api_version` setting, and the previously existing
    :setting:`broker_api_version` setting.

    This means you can now configure the API version for everything
    by setting the :setting:`broker_api_version` setting, while still
    being able to configure the API version individually for producers
    and consumers.

- New :setting:`consumer_api_version` setting.

    See above.

- New :setting:`broker_rebalance_timeout` setting.

- Test improvements

    Contributed by Marcos Schroh (:github_user:`marcosschroh`).

- Documentation improvements by:

    - Bryant Biggs (:github_user:`bryantbiggs`).
    - Christoph Deil (:github_user:`cdeil`).
    - Tim Gates (:github_user:`timgates42`).
    - Marcos Schroh (:github_user:`marcosschroh`).

Fixes
-----

- Consumer: Properly wait for all agents and the table manager to
  start and subscribe to topics before sending subscription list to Kafka.
  (Issue #501).

    This fixes a race condition where the subscription list is sent
    before all agents have started subscribing to the topics they need.
    At worst this result ended in a crash at startup (set
    size changed during iteration).

    Contributed by DhruvaPatil98 (:github_user:`DhruvaPatil98`).

- Agents: Fixed ``Agent.test_context()`` sink support (Issue #495).

    Fix contributed by Denis Kovalev (:github_user:`aikikode`).

- aiokafka: Fixes crash in ``on_span_cancelled_early`` when tracing disabled.

