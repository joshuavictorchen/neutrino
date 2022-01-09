import neutrino
import neutrino.tools as t
import pandas as pd
import requests
import time
from copy import deepcopy
from datetime import datetime
from neutrino.authenticator import Authenticator

MAX_CANDLE_REQUEST = 300


class Link:
    """Creates an API request session and sends/receives API requests/responses.

    The `Coinbase API Reference <https://docs.cloud.coinbase.com/exchange/reference/>`__ provides a comprehensive \
    list of available REST API endpoints.

    The :py:obj:`send_api_request` method may be used to send a generic request to any available endpoint. \
    Pagination is handled automatically.

    Custom methods for requests to specific endpoints are also provided in this class for convenience.

    **Instance attributes:** \n
        * **auth** (*Authenticator*): :py:obj:`neutrino.authenticator.Authenticator` callable.
        * **session** (*str*): :py:obj:`requests.Session` object.

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
            endpoint (str): API request endpoint.
            params (dict(str), optional): API request parameters (varies per request).
            pages (list, optional): Previous data compiled for a paginated requests.

        Returns:
            list: List of API response elements (usually dictionaries).
        """

        # create a fresh list to be returned
        # this needs to be done to prevent carry-over from unrelated API calls, since lists are mutable
        list_response = pages.copy()

        # get the api response
        api_response = self.session.request(
            method,
            neutrino.api_url + endpoint,
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

        # prep data and load into converted_df for each coin
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

    def retrieve_product_candles(
        self, product_id, granularity=60, start=None, end=None, page=None
    ):
        """Gets a DataFrame of a product's historic candle data. \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getproductcandles>`__).

        The Coinbase API limits requests to 300 candles at a time. This function therefore calls itself recursively, \
        as needed, to return all candles within the given ``start`` and ``end`` bounds.

        If no ``end`` bound is given, then the current time is used.

        If no ``start`` bound is given, then ``end`` minus ``granularity`` times 300 is used (i.e., maximum number of data points for one API call).

        Args:
            product_id (str): The coin trading pair (i.e., 'BTC-USD').
            granularity (int, optional): Granularity of the returned candles in seconds. Must be one of the following values: \
                ``60``, ``300``, ``900``, ``3600``, ``21600``, ``86400``.
            start (str, optional): Start bound of the request (``%Y-%m-%d %H:%M``).
            end (str, optional): End bound of the request (``%Y-%m-%d %H:%M``).

        Returns:
            DataFrame: DataFrame with the following columns for each candle: \
                ``time``, ``product_id``, ``low``, ``high``, ``open``, ``close``, ``volume``
        """

        # TODO: add robust error handling

        # determine the maximum number of data points that can be pulled
        max_data_pull = self.calculate_max_candle_pull_minutes(granularity)

        # update start/end bounds if no input was provided
        (start, end) = self.augment_candle_bounds(max_data_pull, start, end)

        # printed_end = min(end, t.add_minutes_to_time_string(start, max_data_pull))
        # print(
        #     f"\n Requesting {product_id} candles from {start} to {printed_end}..."
        # )

        # determine if the number of requested data points exceeds MAX_CANDLE_REQUEST
        recurse = end > t.add_minutes_to_time_string(start, max_data_pull)

        # define the actual start/end parameters which will be passed into the API request
        # retain the original 'start' and 'end' variables to be passed on recursively, if needed
        request_start = start
        request_end = end

        # if recursion is necessary:
        # [1] update request_start to account for fenceposting
        # [2] modify the requested end parameter to keep it within the allowable request bounds
        # [3] update the 'start' variable to the first un-requested timestamp
        #     (this is to set up the next API request)
        if recurse:
            request_start = t.add_minutes_to_time_string(start, -1 * granularity / 60)
            request_end = t.add_minutes_to_time_string(start, max_data_pull)
            start = t.add_minutes_to_time_string(
                start, max_data_pull + (granularity / 60)
            )

        # convert start and end to ISO format
        request_start = t.local_to_ISO_time_string(request_start)
        request_end = t.local_to_ISO_time_string(request_end)

        # generate API request parameters
        params_dict = {
            "granularity": granularity,
            "start": request_start,
            "end": request_end,
        }

        # send API request
        candles_list = self.send_api_request(
            "GET", f"/products/{product_id}/candles", params=params_dict
        )

        # convert retrieved timestamps
        for i in candles_list:
            i[0] = datetime.strftime(datetime.fromtimestamp(i[0]), "%Y-%m-%d %H:%M")

        # create dataframe from API response and sort records from earliest to latest
        candles_df = (
            pd.DataFrame(
                candles_list, columns=["time", "low", "high", "open", "close", "volume"]
            )
            .sort_values(by=["time"], ascending=True)
            .reset_index(drop=True)
        )

        # append candles_df to results from the previous recursive iterations, if they exist
        if isinstance(page, pd.DataFrame):
            candles_df = (
                page.append(candles_df, ignore_index=True)
                .sort_values(by=["time"], ascending=True)
                .reset_index(drop=True)
            )

        # recursively call this function, if needed, to satisfy the initially-supplied pull bounds
        # pass candles_df into the recursed call so that it is carried forward
        if recurse:
            return self.retrieve_product_candles(
                product_id, granularity, start, end, candles_df
            )

        # add product_id as a column and move it to the 1st index
        candles_df["product_id"] = product_id
        t.move_df_column_inplace(candles_df, "product_id", 1)

        return candles_df

    def calculate_max_candle_pull_minutes(self, granularity):
        """Calculate the maximum allowable time range for a single Coinbase API request \
            for the provided granularity. The API allows a maximum pull of 300 time steps per request.

        Args:
            granularity (int, optional): Granularity of the returned candles in seconds. Must be one of the following values: \
                ``60``, ``300``, ``900``, ``3600``, ``21600``, ``86400``.

        Returns:
            int: Maximum allowable time range for a single API request in minutes.
        """

        # granularity / 60 <-- get time in minutes
        # MAX_CANDLE_REQUEST -1 <-- account for fenceposting

        return granularity / 60 * (MAX_CANDLE_REQUEST - 1)

    def augment_candle_bounds(self, max_data_pull, start, end):
        """Update a candle request's ``start`` and ``end`` parameters if none are provided.

        If no ``end`` time is provided, then the current local time is used.

        If no ``start`` time is provided, then ``start`` is set to the earliest time that fits into \
        a single API request, as calculated by the ``end`` time minus ``max_data_pull``.

        Args:
            max_data_pull (int): Maximum allowable time range for a single API request in minutes.
            start (str): Start bound of the request (``%Y-%m-%d %H:%M``).
            end (str): End bound of the request (``%Y-%m-%d %H:%M``).

        Returns:
            tuple (str): Updated ``start`` and ``end`` parameters in the form of ``(start, end)``.
        """

        # if no end is given, then use current time
        if not end:
            end = time.strftime("%Y-%m-%d %H:%M", time.localtime())

        # if no start is given, then use end minus (granularity * max_data_pull)
        if not start:
            start = t.add_minutes_to_time_string(end, -1 * max_data_pull)

        return (start, end)


if __name__ == "__main__":

    pass
