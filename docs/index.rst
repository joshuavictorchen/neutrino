.. toctree::
 :maxdepth: 3

.. warning::

   Documentation has only just begun.

Overview
--------

* **Neutrino** // :py:obj:`neutrino.main.Neutrino`

   * Threads and handles :py:obj:`Streams<neutrino.stream.Stream>` and :py:obj:`Links<neutrino.link.Link>`, and performs operations

* **Stream** // :py:obj:`neutrino.stream.Stream`
   
   * Connects to the Coinbase Pro WebSocket feed and retrieves ticker, order, etc. data.
   * Performs a **minimal** amount of actions as to not fall behind the WebSocket feed.
   * TBD re: if there should be one instance per coin/channel.
   * TBD re: storing a limited amount of internal data.

* **Link** // :py:obj:`neutrino.link.Link`

   * Handles Coinbase Pro API requests.

Neutrino
--------

.. autoclass:: neutrino.main.Neutrino
   :members:
   :undoc-members:
   :show-inheritance:

Stream
------

.. automodule:: neutrino.stream
   :members:
   :undoc-members:
   :show-inheritance:

Link
----

.. automodule:: neutrino.link
   :members:
   :undoc-members:
   :show-inheritance:

Tools
-----

.. automodule:: neutrino.tools
   :members:
   :undoc-members:
   :show-inheritance: