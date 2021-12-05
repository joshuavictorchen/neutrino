import json
import neutrino.tools as t
import pandas as pd
import requests
from datetime import datetime


class Link:
    """Creates an API session and sends/receives API requests/responses.

    *In-depth documentation TBD.*

    Args:
        url (str): Base URL for Coinbase Pro API endpoints.
        auth (Authenticator): :py:obj:`neutrino.tools.Authenticator` callable.

    Instance attributes
        * **name** (*str*): Link's name.
        * **url** (*str*): Base URL for Coinbase Pro API endpoints.
        * **auth** (*str*): :py:obj:`neutrino.tools.Authenticator` callable.
        * **session** (*str*): API Session object.
        * **accounts** (*str*): TBD
        * **coins** (*str*): TBD
    """

    def __init__(self, name, url, auth):

        self.name = name
        self.url = url
        self.auth = auth
        self.session = requests.Session()
        self.accounts = {}
        self.coins = {}

    def send_api_request(self, method, endpoint, params=None, data=None):
        """Sends an API request and returns the response.

        Args:
            method (string): API request method ('get', 'post', etc.).
            endpoint (string): API request endpoint.
            params (list(str), optional): *description TBD* Defaults to None.
            data (list(str), optional): *description TBD*. Defaults to None.

        Returns:
            str: API response.
        """

        return self.session.request(
            method,
            self.url + endpoint,
            params=params,
            data=data,
            auth=self.auth,
            timeout=30,
        )

    def get_user_accounts(self, filter_empty_accounts=True):
        """get all currency account IDs for user"""

        # obtain the API response as a list of dicts
        account_list = json.loads(self.send_api_request("GET", "/accounts").text)

        account_dict = {}
        [account_dict.update({i.get("currency"): i}) for i in account_list]

        if filter_empty_accounts:
            account_dict = {
                key: value
                for key, value in account_dict.items()
                if float(value.get("balance")) != 0
            }

        self.accounts = account_dict
        return account_dict

    def get_orders(self, **kwargs):
        """get all open orders for the authenticated account"""

        orders_list = json.loads(
            self.send_api_request("GET", "/orders", params=kwargs).text
        )

        orders_dict = {}
        for i in orders_list:
            if orders_dict.get(i.get("product_id")):
                orders_dict.get(i.get("product_id")).update({i.get("id"): i})
            else:
                orders_dict.update({i.get("product_id"): {i.get("id"): i}})

        return orders_dict

    def get_account_ledger(self, account_id):
        """get the ledger (transaction history) for the specified user account"""

        # TODO: add method to get user account ID
        # TODO: add pagination method

        ledger_list = json.loads(
            self.send_api_request("GET", f"/accounts/{account_id}/ledger").text
        )

        ledger_dict = {}
        [ledger_dict.update({i.get("id"): i}) for i in ledger_list]

        return ledger_dict

    def get_transfers(self, **kwargs):
        """get all fund transfers for the authenticated account"""

        transfers_list = json.loads(
            self.send_api_request("GET", "/transfers", params=kwargs).text
        )

        transfers_dict = {}
        for i in transfers_list:
            transfers_dict.update({i.get("id"): i})

        return transfers_dict

    def get_fees(self, **kwargs):
        """get all fee rates and 30-day trade volume for the authenticated account"""

        fees_dict = json.loads(
            self.send_api_request("GET", "/fees", params=kwargs).text
        )

        return fees_dict

    def get_product_candles(self, product_id, granularity=60, start=None, end=None):
        """get historical product candles"""

        if start:
            start = t.local_to_ISO_time_strings(start)

        if end:
            end = t.local_to_ISO_time_strings(end)

        params_dict = {"granularity": granularity, "start": start, "end": end}

        candles_list = json.loads(
            self.send_api_request(
                "GET", f"/products/{product_id}/candles", params=params_dict
            ).text
        )

        for i in candles_list:
            i[0] = datetime.strftime(datetime.fromtimestamp(i[0]), "%Y-%m-%d %H:%M")

        candles_df = pd.DataFrame(
            candles_list, columns=["time", "low", "high", "open", "close", "volume"]
        )

        return candles_df


if __name__ == "__main__":

    pass
