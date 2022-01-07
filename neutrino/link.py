import neutrino.tools as t
import pandas as pd
import requests
import time
from datetime import datetime
from pathlib import Path

MAX_CANDLE_REQUEST = 300


class Link:
    """Creates an API request session and sends/receives API requests/responses.

    The `Coinbase API Reference <https://docs.cloud.coinbase.com/exchange/reference/>`__ provides a comprehensive \
    list of available REST API endpoints.

    The :py:obj:`send_api_request` method may be used to send a generic request to any available endpoint. \
    Pagination is handled automatically.

    Custom methods for requests to specific endpoints are also provided in this class for convenience.

    **Instance attributes:** \n
        * **api_url** (*str*): Base URL for Coinbase Pro API endpoints.
        * **auth** (*Authenticator*): :py:obj:`neutrino.tools.Authenticator` callable.
        * **database_path** (*Path*): :py:obj:`Path` object containing the absolute filepath to the folder \
            to which the Link exports CSV files.
        * **session** (*str*): :py:obj:`requests.Session` object.

    Args:
        url (str): Base URL for Coinbase Pro API endpoints.
        cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`neutrino.tools.Authenticator`.
        database_path (Path): :py:obj:`Path` object containing the absolute filepath to the folder \
            to which the Link exports CSV files.
    """

    def __init__(self, url, cbkey_set, database_path):

        self.api_url = url
        self.update_auth(cbkey_set)
        self.update_database_path(database_path)
        self.session = requests.Session()

    def update_auth(self, cbkey_set):
        """Updates the :py:obj:`Link`'s :py:obj:`Authenticator<neutrino.tools.Authenticator>` \
            callable with new keys for authenticating Coinbase WebSocket and API requests.

        Args:
            cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`neutrino.tools.Authenticator`.
        """

        self.auth = t.Authenticator(cbkey_set)

    def update_database_path(self, database_path):
        """Update the filepath to the folder to which the :py:obj:`Link` exports CSV files.

        Args:
            database_path (str): Absolute filepath to the folder to which the :py:obj:`Link` \
                exports CSV files.
        """

        self.database_path = Path(database_path)

    def send_api_request(self, method, endpoint, params=None, pages=[]):
        """Sends an API request to the specified Coinbase Exchange endpoint and returns the response.

        `Paginated requests <https://docs.cloud.coinbase.com/exchange/docs/pagination>`__ are handled recursively; \
        this method iterates through all available ``after`` cursors for a request.

        This method returns a list of API response elements, which are usually dictionaries but can be of other types \
        depending on the specific request.

        Args:
            method (str): API request method (``get``, ``post``, etc.).
            endpoint (str): API request endpoint.
            params (list(str), optional): API request parameters (varies per request).
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
            self.api_url + endpoint,
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

    def request_accounts(self):
        """Sends a request to retrieve all trading accounts and their holdings for the authenticated :py:obj:`Link`'s profile \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccounts>`__).

        Returns:
            list (dict): List of dictionaries corresponding to the API response headers below:
            
            .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                                 id: required
                           currency: required
                            balance: required
                               hold: required
                          available: required
                         profile_id: required
                    trading_enabled: required
                }
        """

        return self.send_api_request("GET", "/accounts")

    def request_account_by_id(self, account_id):
        """Sends a request to retrieve a dictionary with information pertaining to a specific ``account_id`` \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccount>`__).

        Args:
            account_id (str): Trading account ID for a given coin.

        Returns:
            dict (str): .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                                 id: required
                           currency: required
                            balance: required
                               hold: required
                          available: required
                         profile_id: required
                    trading_enabled: required
                }
        """

        return self.send_api_request("GET", f"/accounts/{account_id}")[0]

    def request_account_ledger(self, account_id, **kwargs):
        """Sends a request to retrieve all ledger activity (anything that would affect the account's balance) for a given coin account \
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
            list (dict): List of dictionaries corresponding to the API response headers below:
            
            .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                            id: required (note: this is the transaction id and not the account id)
                        amount: required
                    created_at: required, ISO 8601
                       balance: required
                          type: required
                       details: {
                                            order_id: required
                                          product_id: required
                                            trade_id: required
                                         transfer_id:
                                       transfer_type:
                                          account_id:
                        }
                }
        """

        return self.send_api_request(
            "GET", f"/accounts/{account_id}/ledger", params=kwargs
        )

    def request_transfers(self):
        """Sends a request to retrieve in-progress and completed transfers of funds in/out of any of the authenticated :py:obj:`Link`'s accounts \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_gettransfers>`__).

        .. note::

            The returned :py:obj:`<activity id>` ``details`` requirements are not explicitly documented \
                in the API Reference. They have been determined via user observation.

        Args:
            save (bool, optional): Export the returned DataFrame to a CSV file in the directory specified by ``self.database_path``.

        Returns:
            list (dict): List of dictionaries corresponding to the API response headers below:

            .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
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
        """

        return self.send_api_request("GET", "/transfers")

    def request_orders(self, **kwargs):
        """Sends a request to retrieve orders associated with the authenticated :py:obj:`Link` \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getorders>`__).

        All current and historical orders are returned by default. This is distinct from the Coinbase API's default \
        behavior, which only returns open orders by default.

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
            list (dict): List of dictionaries corresponding to the API response headers below:
            
            .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
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
        """

        # default to getting all orders if no 'status' kwarg is provided
        if not kwargs.get("status"):
            kwargs["status"] = ["all"]

        return self.send_api_request("GET", "/orders", params=kwargs)

    def request_fees(self):
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

        return self.send_api_request("GET", "/fees")[0]

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
