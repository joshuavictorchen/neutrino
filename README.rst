|Build Status|

neutrino
--------

This project is under construction. `Initial documentation can be found here <https://joshuavictorchen.github.io/neutrino/>`_.

Overview
--------

The **neutrino** is a prototype framework that creates custom cryptocurrency tracking charts and executes \
data-driven orders via the Coinbase Pro platform. **It is currently under development.**

The first goal of this program is to provide actionable views that are not readily available \
on most of the major exchanges, such as:

1. What is my total cost basis for X currency in terms of USD, considering all historical trades on this account \
   (including crypto-to-crypto transactions)? What is my overall gain/loss given the current market prices?  

2. What is the gain/loss of X currency's value *from the perspective of Y point in time*? \
   Popular views show the 24-hour delta, but this moving window can lead to misleading reports. \
   For example, a currency may show an increasingly positive 24-hour delta despite a present decline \
   in price, provided there was a more servere drop 24 hours ago and a subsequent recovery in between.

3. How are XYZ currencies performing *relative to each other, from the perspective of Y point in time*?

These are relatively simple examples, but one can imagine the usefulness of this data as a starting point \
for constructing meaningful portfolio trackers and trading algorithms. At the risk of derailing this high-level \
overview, here's a simple prototype view that shows the performance of various currencies relative to BTC \
using a fixed frame of reference:


.. figure:: docs/_images/proto-view.jpg


This kind of view gives a clear apples-to-apples performace comparison across currencies, and eliminates the \
moving window problem by using a fixed reference point in time. This particular chart is useful for traders who \
prefer BTC over fiat.

Development Approach
--------------------

Formation of the **neutrino** is taking place across three phrases. It is currently in **Phase 1**, \
as is evident by its lack of unit tests and meaningful documentation:

Phase 1 - Initial development
    * Framework and tooling
    * Data pulling features
    * Prototype CLI
    * Unit tests and documentation
   
Phase 2 - Reporting and analytics
    * Local database configuration
    * Analytics tooling
    * Reporting views and features
    * User manual

Phase 3 - Data-driven actions
    * Data posting features
    * Trading algorithms and implementation

Screenshots of the prototype CLI can be found in the `initial documentation here <https://joshuavictorchen.github.io/neutrino/>`_.

.. |Build Status| image:: https://github.com/joshuavictorchen/neutrino/actions/workflows/main.yml/badge.svg?branch=master
    :target: https://github.com/joshuavictorchen/neutrino/actions/workflows/main.yml