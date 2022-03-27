|Build Status|

neutrino
--------

This project is under construction. `Initial documentation can be found here <https://joshuavictorchen.github.io/neutrino/>`_.

Overview
--------

The **neutrino** is a prototype framework that creates custom cryptocurrency portfolio health reports and executes
data-driven orders via the Coinbase Pro platform. **It is currently under development.**

An immediate goal of this program is to provide actionable views that are not readily available
on most of the major exchanges, such as:

1. What is my total cost basis for N currency in terms of USD, considering all historical trades on my account
   *including crypto-to-crypto transactions*? What is my overall gain/loss given current market prices?

2. What is the gain/loss of N currency's value *from X reference point in time*?
   Popular views show the 24-hour delta, but this moving window can lead to misleading reports.
   For example, a currency can see an increasingly positive 24-hour delta while simultaneously decreasing
   in price, provided there was a more servere downtrend 24 hours ago and a subsequent recovery in between.

3. How are N..(N+n) currencies performing *relative to each other, from X reference point in time*?

For example, here's a simple prototype chart that shows the performance of various currencies relative to BTC
with respect to a given point in time. This type of view provides clear apples-to-apples comparisons re:
currency performance, and eliminates the moving window problem by using a fixed reference point in time.
This particular chart is useful for traders who prefer BTC over fiat:

.. figure:: docs/_images/proto-view.jpg

Development Approach
--------------------

Formation of the **neutrino** is taking place across three phrases. It is currently in **Phase 1**, 
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