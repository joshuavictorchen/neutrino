import neutrino
import neutrino.tools as t
import pandas as pd
import requests
from copy import deepcopy
from neutrino.authenticator import Authenticator


class Link:
    """Creates an API request session and sends/receives API requests/responses.

    The `Coinbase API Reference <https://docs.cloud.coinbase.com/exchange/reference/>`__ provides a comprehensive \
    list of available REST API endpoints.

    The :py:obj:`send_api_request` method may be used to send a generic request to any available endpoint. \
    Pagination is handled automatically.

    **Instance attributes:** \n
        * **auth** (*Authenticator*): :py:obj:`neutrino.authenticator.Authenticator` callable.
        * **session** (*str*): :py:obj:`requests.Session` object for API requests.

    Args:
        cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`neutrino.authenticator.Authenticator`.
    """

    def __init__(self, cbkey_set):

        self.update_auth(cbkey_set)
        self.session = requests.Session()

    def update_auth(self, cbkey_set):
        """Updates the :py:obj:`Link`'s :py:obj:`Authenticator<neutrino.authenticator.Authenticator>` \
            callable with new keys for authenticating Coinbase WebSocket and API requests.

        Args:
            cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`neutrino.authenticator.Authenticator`.
        """

        self.auth = Authenticator(cbkey_set)

    def send_api_request(self, method, endpoint, params=None, pages=[]):
        """Sends an API request to the specified Coinbase Exchange endpoint and returns the response.

        `Paginated requests <https://docs.cloud.coinbase.com/exchange/docs/pagination>`__ are handled recursively; \
        this method iterates through all available ``after`` cursors for a request.

        This method returns a list of API response elements, which are usually dictionaries but can be of other types \
        depending on the specific request.

        Args:
            method (str): API request method (``get``, ``post``, etc.).
            endpoint (str): API request endpoint, with no leading ``/`` (i.e., "accounts").
            params (dict(str), optional): API request parameters (varies per request).
            pages (list, optional): Previous data compiled for a paginated requests.

        Returns:
            list: List of API response elements (usually dictionaries).
        """

        # create a fresh list to be returned
        # this needs to be done to prevent carry-over from unrelated API calls, since lists are mutable
        list_response = pages.copy()

        # print request to console
        print(f"\n Sending API request: {method} {endpoint}", end="")
        if params:
            t.print_recursive_dict(params)
        else:
            print()

        # get the api response
        api_response = self.session.request(
            method,
            neutrino.api_url + "/" + endpoint,
            params=params,
            auth=self.auth,
            timeout=30,
        )

        # append or extend this to the list to be returned, depending on the response type
        if type(api_response.json()) == dict:
            list_response.append(api_response.json())
        else:
            list_response.extend(api_response.json())

        # if there are no 'cb-after' headers, then there is nothing to be paginated, and list_response can be returned
        if not api_response.headers.get("cb-after"):
            return list_response

        # otherwise, perform this function recursively until pagination is exhausted
        else:

            # update the parameters supplied to the recursive call, preserving other parameters, if they exist
            if params is None:
                params = {"after": api_response.headers.get("cb-after")}
            else:
                params["after"] = api_response.headers.get("cb-after")

            # recursively call this function, carrying the list_response forward so that all 'pages' are returned at the end
            return self.send_api_request(
                method, endpoint, params=params, pages=list_response
            )

    def convert_API_response_list_to_df(self, response_list, main_key):
        """Converts a list of dicts from a Coinbase API response to a DataFrame.

        Args:
            response_list (list(dict)): Response from a Coinbase API request.
            main_key (str): Key containing a unique identifier for a response element.

        Returns:
            DataFrame: DataFrame of values loaded from a Coinbase API response.
        """

        # create a deepcopy in order to prevent carry-over to/from unrelated method calls, since lists are mutable
        response_list = deepcopy(response_list)

        # convert list of dicts into dict of dicts
        data_dict = {}
        [data_dict.update({i.get(main_key): i}) for i in response_list]

        # create a df object to load data into
        converted_df = pd.DataFrame()

        # prep data and load into converted_df
        for data_value_dict in data_dict.values():

            for key, value in data_value_dict.copy().items():

                # the Coinbase API nests multiple items under a 'details' key for certain responses
                # un-nest these items and delete the 'details' key for these cases
                # finally, put all values into list format so that they can be loaded via pd.DataFrame.from_dict()
                if key == "details":
                    for inner_key, inner_value in value.items():
                        data_value_dict[inner_key] = [inner_value]
                    data_value_dict.pop(key, None)
                else:
                    data_value_dict[key] = [value]

            # add this data to the df object
            converted_df = converted_df.append(
                pd.DataFrame.from_dict(data_value_dict), ignore_index=True
            )

        return converted_df


if __name__ == "__main__":

    pass
