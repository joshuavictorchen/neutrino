import json
import neutrino.tools as t
import pandas as pd
import requests
from datetime import datetime


class Link:
    """Creates an API session and sends/receives API requests/responses.

    **Instance attributes:** \n
        * **name** (*str*): :py:obj:`Link`'s name.
        * **url** (*str*): Base URL for Coinbase Pro API endpoints.
        * **auth** (*str*): :py:obj:`neutrino.tools.Authenticator` callable.
        * **session** (*str*): :py:obj:`requests.Session` object.
        * **coins** (*dict(str)*): To be implemented - dict for each coin containing account info, orders, transfers.

    Args:
        url (str): Base URL for Coinbase Pro API endpoints.
        auth (Authenticator): :py:obj:`neutrino.tools.Authenticator` callable.
    """

    def __init__(self, name, url, auth):

        self.name = name
        self.url = url
        self.auth = auth
        self.session = requests.Session()
        self.coins = {}

    def send_api_request(self, method, endpoint, params=None):
        """Sends an API request to the specified Coinbase Exchange endpoint and returns the response.

        Args:
            method (string): API request method (``get``, ``post``, etc.).
            endpoint (string): API request endpoint.
            params (list(str), optional): API request parameters (varies per request).

        Returns:
            dict: API response loaded into a dict.
        """

        return json.loads(
            self.session.request(
                method,
                self.url + endpoint,
                params=params,
                auth=self.auth,
                timeout=30,
            ).text
        )

    def get_accounts(self, exclude_empty_accounts=False):
        """Gets a dict of all trading accounts and their holdings for the authenticated :py:obj:`Link` \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccounts>`_).

        .. admonition:: TODO

            * Append/update this information to :py:obj:`self.coins`.

        Args:
            exclude_empty_accounts (bool, optional): The API retuns all accounts for all available coins by default. \
                Set this to ``True`` to exclude zero-balance accounts from the returned result.

        Returns:
            dict (for N number of :py:obj:`<coin name>`): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                    <coin name> (str): {
                                      id (str): required
                                currency (str): required
                                 balance (str): required
                                    hold (str): required
                               available (str): required
                              profile_id (str): required
                        trading_enabled (bool): required
                    }
                }
        """

        # obtain the API response as a list of dicts
        account_list = self.send_api_request("GET", "/accounts")

        account_dict = {}
        [account_dict.update({i.get("currency"): i}) for i in account_list]

        if exclude_empty_accounts:
            account_dict = {
                key: value
                for key, value in account_dict.items()
                if float(value.get("balance")) != 0
            }

        # TODO: append/update this information to self.coins

        return account_dict

    def get_account_ledger(self, account_id):
        """get the ledger (transaction history) for the specified user account"""

        # TODO: add method to get user account ID
        # TODO: add pagination method

        ledger_list = self.send_api_request("GET", f"/accounts/{account_id}/ledger")

        ledger_dict = {}
        [ledger_dict.update({i.get("id"): i}) for i in ledger_list]

        return ledger_dict

    def get_account_transfers(self, **kwargs):
        """get all fund transfers for the authenticated account"""

        transfers_list = self.send_api_request("GET", "/transfers", params=kwargs)

        transfers_dict = {}
        for i in transfers_list:
            transfers_dict.update({i.get("id"): i})

        return transfers_dict

    def get_orders(self, **kwargs):
        """Gets a dict of orders associated with the authenticated :py:obj:`Link` \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getorders>`_).

        .. admonition:: TODO

            * `Handle pagination <https://docs.cloud.coinbase.com/exchange/docs/pagination>`_.

        Args:
            **kwargs (various, optional):
                * **profile_id** (*str*): Filter results by a specific ``profile_id``.
                * **product_id** (*str*): Filter results by a specific ``product_id``.
                * **sortedBy** (*str*): Sort criteria for results: \
                    ``created_at``, ``price``, ``size``, ``order_id``, ``side``, ``type``.
                * **sorting** (*str*): Sort results by ``asc`` or ``desc``.
                * **start_date** (*str*): Filter results by minimum posted date (``%Y-%m-%d %H:%M``).
                * **end_date** (*str*): Filter results by maximum posted date (``%Y-%m-%d %H:%M``).
                * **before** (*str*): Used for pagination. Sets start cursor to ``before`` date.
                * **after** (*str*): Used for pagination. Sets end cursor to ``after`` date.
                * **limit** (*int*): Limit on number of results to return.
                * **status** (*list(str)*): List of order statuses to filter by: \
                    ``open``, ``pending``, ``rejected``, ``done``, ``active``, ``received``, ``all``.

        Returns:
            dict (for N number of :py:obj:`<order id>`): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                    <order id> (str): {
                                     id (str): required
                                  price (str):
                                   size (str):
                             product_id (str): required
                             profile_id (str):
                                   side (str): required
                                  funds (str):
                        specified_funds (str):
                                   type (str): required
                             post_only (bool): required
                             created_at (str): required, ISO 8601
                                done_at (str):
                            done_reason (str):
                          reject_reason (str):
                              fill_fees (str): required
                            filled_size (str): required
                         executed_value (str):
                                 status (str): required
                               settled (bool): required
                                   stop (str):
                             stop_price (str):
                         funding_amount (str):
                    }
                }

        """

        orders_list = self.send_api_request("GET", "/orders", params=kwargs)

        orders_dict = {}
        for i in orders_list:
            if orders_dict.get(i.get("product_id")):
                orders_dict.get(i.get("product_id")).update({i.get("id"): i})
            else:
                orders_dict.update({i.get("product_id"): {i.get("id"): i}})

        return orders_dict

    def get_fees(self, **kwargs):
        """get all fee rates and 30-day trade volume for the authenticated account"""

        fees_dict = self.send_api_request("GET", "/fees", params=kwargs)

        return fees_dict

    def get_product_candles(self, product_id, granularity=60, start=None, end=None):
        """get historical product candles"""

        if start:
            start = t.local_to_ISO_time_strings(start)

        if end:
            end = t.local_to_ISO_time_strings(end)

        params_dict = {"granularity": granularity, "start": start, "end": end}

        candles_list = self.send_api_request(
            "GET", f"/products/{product_id}/candles", params=params_dict
        )

        for i in candles_list:
            i[0] = datetime.strftime(datetime.fromtimestamp(i[0]), "%Y-%m-%d %H:%M")

        candles_df = pd.DataFrame(
            candles_list, columns=["time", "low", "high", "open", "close", "volume"]
        )

        return candles_df


if __name__ == "__main__":

    pass
