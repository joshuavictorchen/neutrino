.. toctree::
 :maxdepth: 3

.. warning::

   Documentation contains many incorrect references and descriptions.
   
   User manual is nonexistent.
   
   This is a proof-of-concept and not intended to be used for anything - yet.

Overview
--------

* **Neutrino** // :py:obj:`neutrino.main.Neutrino`

   * Manages :py:obj:`Streams<neutrino.stream.Stream>` and inherits from :py:obj:`Link<neutrino.link.Link>`.
   * Performs operations as directed by the user.
   * TBD re: data structure.

* **Stream** // :py:obj:`neutrino.stream.Stream`
   
   * Connects to the Coinbase Pro WebSocket feed and retrieves ticker, order, etc. data.
   * Performs a **minimal** amount of actions as to not fall behind the WebSocket feed.
   * TBD re: if there should be one instance per coin/channel.
   * TBD re: storing a limited amount of internal data.

* **Link** // :py:obj:`neutrino.link.Link`

   * Handles Coinbase Pro API requests. Used to get account information, place orders, etc.

Neutrino
--------

.. autoclass:: neutrino.main.Neutrino
   :members:
   :undoc-members:
   :show-inheritance:

Datum
-----

.. automodule:: neutrino.datum
   :members:
   :undoc-members:
   :show-inheritance:

Link
----

.. automodule:: neutrino.link
   :members:
   :undoc-members:
   :show-inheritance:

Stream
------

.. automodule:: neutrino.stream
   :members:
   :undoc-members:
   :show-inheritance:

Authenticator
-------------

.. automodule:: neutrino.authenticator
   :members:
   :undoc-members:
   :show-inheritance:

Updater
-------

.. automodule:: neutrino.updater
   :members:
   :undoc-members:
   :show-inheritance:

Tools
-----

.. automodule:: neutrino.tools
   :members:
   :undoc-members:
   :show-inheritance: