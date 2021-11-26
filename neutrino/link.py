import neutrino.tools as t
from threading import Thread
from websocket import create_connection
import requests
import traceback
import json
import time
from neutrino.stream import Stream


class Link:
    def __init__(self, url, auth):

        self.session = requests.Session()
        self.accounts = None
        self.coins = {}
        self.url = url
        self.auth = auth

    def send_api_request(self, method, endpoint, params=None, data=None):
        """send an API request and return the results"""

        # TODO: check for errors

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

    def get_test(self):
        """temporary test method"""

        return json.loads(self.send_api_request("GET", "/coinbase-accounts").text)

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


if __name__ == "__main__":

    pass
