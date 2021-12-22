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
        * **coins** (*dict*): To be implemented - dict for each coin containing account info, orders, transfers.

    .. admonition:: TODO

        * Implement overarching :py:obj:`self.coins`.

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
            method (str): API request method (``get``, ``post``, etc.).
            endpoint (str): API request endpoint.
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
        """Gets a dict of all trading accounts and their holdings for the authenticated :py:obj:`Link`'s profile \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccounts>`__).

        Args:
            exclude_empty_accounts (bool, optional): The API retuns all accounts for all available coins by default. \
                Set this to :py:obj:`True` to exclude zero-balance accounts from the returned result.

        Returns:
            dict (for N number of :py:obj:`<coin name>`): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                    <coin name>: {
                                      id: required
                                currency: required
                                 balance: required
                                    hold: required
                               available: required
                              profile_id: required
                         trading_enabled: required
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

    def get_account_ledger(self, account_id, **kwargs):
        """Gets a dict of ledger activity (anything that would affect the account's balance) for a given coin account \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccountledger>`__).

        Args:
            account_id (str): Trading account ID for a given coin.
            **kwargs (various, optional):
                * **start_date** (*str*): Filter by minimum posted date (``%Y-%m-%d %H:%M``).
                * **end_date** (*str*): Filter by maximum posted date (``%Y-%m-%d %H:%M``).
                * **before** (*str*): Used for pagination. Sets start cursor to ``before`` date.
                * **after** (*str*): Used for pagination. Sets end cursor to ``after`` date.
                * **limit** (*int*): Limit on number of results to return.
                * **profile_id** (*str*): Filter results by a specific ``profile_id``.

        Returns:
            dict (for N number of :py:obj:`<activity id>`): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                    <activity id>: {
                                id: required
                           armount: required
                        created_at: required, ISO 8601
                           balance: required
                              type: required
                           details: {
                                order_id: required
                              product_id: required
                                trade_id: required
                           }
                    }
                }
        """

        ledger_list = self.send_api_request(
            "GET", f"/accounts/{account_id}/ledger", params=kwargs
        )

        ledger_dict = {}
        [ledger_dict.update({i.get("id"): i}) for i in ledger_list]

        # TODO: append/update this information to self.coins

        return ledger_dict

    def get_account_transfers(self):
        """Gets a dict of in-progress and completed transfers of funds in/out of any of the authenticated :py:obj:`Link`'s accounts \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_gettransfers>`__).

        .. note::

            The returned :py:obj:`<activity id>` ``details`` requirements are not explicitly documented \
                in the API Reference. They have been determined via user observation.

        Returns:
            dict (for N number of :py:obj:`<activity id>`): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                    <activity id>: {
                                  id: required
                                type: required
                          created_at: required, ISO 8601
                        completed_at: required, ISO 8601
                         canceled_at: required, ISO 8601
                        processed_at: required, ISO 8601
                              amount: required
                             details: {
                                              is_instant_usd:
                                          coinbase_payout_at:
                                         coinbase_account_id: required
                                        coinbase_deposity_id:
                                     coinbase_transaction_id: required
                                  coinbase_payment_method_id:
                                coinbase_payment_method_type: required
                            }
                          user_nonce: required
                    }
                }
        """

        transfers_list = self.send_api_request("GET", "/transfers")

        transfers_dict = {}
        for i in transfers_list:
            transfers_dict.update({i.get("id"): i})

        return transfers_dict

    def get_orders(self, **kwargs):
        """Gets a dict of orders associated with the authenticated :py:obj:`Link` \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getorders>`__).

        .. admonition:: TODO

            * `Handle pagination <https://docs.cloud.coinbase.com/exchange/docs/pagination>`__.

        Args:
            **kwargs (various, optional):
                * **profile_id** (*str*): Filter results by a specific ``profile_id``.
                * **product_id** (*str*): Filter results by a specific ``product_id``.
                * **sortedBy** (*str*): Sort criteria for results: \
                    ``created_at``, ``price``, ``size``, ``order_id``, ``side``, ``type``.
                * **sorting** (*str*): Sort results by ``asc`` or ``desc``.
                * **start_date** (*str*): Filter by minimum posted date (``%Y-%m-%d %H:%M``).
                * **end_date** (*str*): Filter by maximum posted date (``%Y-%m-%d %H:%M``).
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
                    <order id>: {
                                     id: required
                                  price:
                                   size:
                             product_id: required
                             profile_id:
                                   side: required
                                  funds:
                        specified_funds:
                                   type: required
                              post_only: required
                             created_at: required, ISO 8601
                                done_at:
                            done_reason:
                          reject_reason:
                              fill_fees: required
                            filled_size: required
                         executed_value:
                                 status: required
                                settled: required
                                   stop:
                             stop_price:
                         funding_amount:
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

        # TODO: append/update this information to self.coins

        return orders_dict

    def get_fees(self):
        """Gets the fee rates and 30-day trailing volume for the authenticated :py:obj:`Link`'s profile \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getfees>`__).

        Returns:
            dict (str): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                    taker_fee_rate: required
                    maker_fee_rate: required
                        usd_volume: 
                }
        """

        fees_dict = self.send_api_request("GET", "/fees")

        return fees_dict

    def get_product_candles(self, product_id, granularity=60, start=None, end=None):
        """Gets a DataFrame of a product's historic candle data. Returns a maximum of 300 candles per request \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getproductcandles>`__).

        .. admonition:: TODO

            * Configure and document default start/end parameters.
            * Configure 'pagination' for >300 candle requests.

        Args:
            product_id (str): The coin trading pair (i.e., 'BTC-USD').
            granularity (int, optional): Granularity of the returned candles in seconds. Must be one of the following values: \
                ``60``, ``300``, ``900``, ``3600``, ``21600``, ``86400``.
            start (str, optional): Start bound of the request (``%Y-%m-%d %H:%M``).
            end (str, optional): End bound of the request (``%Y-%m-%d %H:%M``).

        Returns:
            DataFrame: DataFrame with the following columns for each candle: \
                ``time``, ``low``, ``high``, ``open``, ``close``, ``volume``
        """

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
