import neutrino.tools as t
import pandas as pd
import requests
import time
from datetime import datetime

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
MAX_CANDLE_REQUEST = 300


class Link:
    """Creates an API session and sends/receives API requests/responses.

    **Instance attributes:** \n
        * **name** (*str*): :py:obj:`Link`'s name.
        * **verbose** (*bool*): If ``True``, then API responses are printed to the console.
        * **url** (*str*): Base URL for Coinbase Pro API endpoints.
        * **auth** (*Authenticator*): :py:obj:`neutrino.tools.Authenticator` callable.
        * **session** (*str*): :py:obj:`requests.Session` object.

    Args:
        url (str): Base URL for Coinbase Pro API endpoints.
        auth (Authenticator): :py:obj:`neutrino.tools.Authenticator` callable.
    """

    def __init__(self, name, url, auth, verbose=True):

        self.name = name
        self.verbose = verbose
        self.url = url
        self.update_auth(auth)
        self.session = requests.Session()

    def set_verbosity(self, verbose):
        """Updates Link's behavior to print (or not pring) formatted API responses to the console.

        Args:
            verbose (bool): ``True`` if print statements are desired.
        """

        self.verbose = verbose

        verb = "begin" if verbose else "stop"
        print(f"\n Link {self.name} will {verb} printing API responses to the console.")

    def update_auth(self, auth):
        """Update authentication for the link.

        Args:
            auth (Authenticator): :py:obj:`neutrino.tools.Authenticator` callable.
        """

        self.auth = auth

    def send_api_request(self, method, endpoint, params=None, pages=[]):
        """Sends an API request to the specified Coinbase Exchange endpoint and returns the response.

        `Paginated requests <https://docs.cloud.coinbase.com/exchange/docs/pagination>`__ are handled recursively; \
        this method iterates through all available ``after`` cursors for a request.

        This method returns a list of API response elements, which are usually dictionaries but can be other types \
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
            self.url + endpoint,
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

    def load_df_from_API_response_list(self, response_list, main_key):
        """Converts a list of dicts from a Coinbase API response to a DataFrame.

        Args:
            response_list (list(dict)): Response from a Coinbase API request.
            main_key (str): Key containing a unique identifier for a response element.

        Returns:
            DataFrame: DataFrame of values loaded from a Coinbase API response.
        """

        # convert list of dicts into dict of dicts
        data_dict = {}
        [data_dict.update({i.get(main_key): i}) for i in response_list]

        # create a df object to load data into
        loaded_df = pd.DataFrame()

        # prep data and load into loaded_df for each coin
        for data_value_dict in data_dict.values():

            for key, value in data_value_dict.copy().items():

                # the Coinbase API nests multiple items under a 'details' key for certain responses
                # un-nest these items and delete the 'details' key for these cases
                if key == "details":
                    for inner_key, inner_value in value.items():
                        data_value_dict[inner_key] = [inner_value]
                    data_value_dict.pop(key, None)
                else:
                    data_value_dict[key] = [value]

            # add this data to the df object
            loaded_df = loaded_df.append(
                pd.DataFrame.from_dict(data_value_dict), ignore_index=True
            )

        return loaded_df

    def get_accounts(self, exclude_empty_accounts=False):
        """Loads a DataFrame with all trading accounts and their holdings for the authenticated :py:obj:`Link`'s profile \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccounts>`__).

        Args:
            exclude_empty_accounts (bool, optional): The API retuns all accounts for all available coins by default. \
                Set this to :py:obj:`True` to exclude zero-balance accounts from the returned result.

        Returns:
            DataFrame: DataFrame with columns corresponding to the headers listed below:
            
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

        # obtain the API response as a list of dicts
        account_list = self.send_api_request("GET", "/accounts")

        # load data into df
        account_df = self.load_df_from_API_response_list(account_list, "currency")

        # exclude accounts with <= 0 balance, if applicable
        if exclude_empty_accounts:
            account_df = account_df[
                account_df["balance"].astype(float) > 0
            ].reset_index(drop=True)

        if self.verbose:
            print(account_df)

        return account_df

    def get_account_ledger(self, account_id, **kwargs):
        """Loads a DataFrame with all ledger activity (anything that would affect the account's balance) for a given coin account \
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
            DataFrame: DataFrame with columns corresponding to the headers listed below. \
            Note that the ``details`` values are treated as columns in the returned DataFrame:
            
            .. code-block::

                # key definitions can be found in API Reference link above
                # types, response requirements, and notes are described below

                {
                            id: required
                        amount: required
                    created_at: required, ISO 8601
                       balance: required
                          type: required
                       details: {
                                       order_id: required
                                     product_id: required
                                       trade_id: required
                        }
                }
        """

        # obtain the API response as a list of dicts
        ledger_list = self.send_api_request(
            "GET", f"/accounts/{account_id}/ledger", params=kwargs
        )

        # load data into df
        ledger_df = self.load_df_from_API_response_list(ledger_list, "id")

        if self.verbose:
            print(ledger_df)

        return ledger_df

    def get_account_transfers(self):
        """Loads a DataFrame with in-progress and completed transfers of funds in/out of any of the authenticated :py:obj:`Link`'s accounts \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_gettransfers>`__).

        .. note::

            The returned :py:obj:`<activity id>` ``details`` requirements are not explicitly documented \
                in the API Reference. They have been determined via user observation.

        Returns:
            DataFrame: DataFrame with columns corresponding to the headers listed below. \
            Note that the ``details`` values are treated as columns in the returned DataFrame:

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
        # obtain the API response as a list of dicts
        transfers_list = self.send_api_request("GET", "/transfers")

        # load data into df
        transfers_df = self.load_df_from_API_response_list(transfers_list, "id")

        if self.verbose:
            print(transfers_df)

        return transfers_df

    def get_orders(self, **kwargs):
        """Loads a DataFrame with orders associated with the authenticated :py:obj:`Link` \
            (`API Reference <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getorders>`__).

        .. note::
        
            Only open or un-settled orders are returned by default. Specify ``status=["all"]`` in the method call \
            to return all orders.

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
            DataFrame: DataFrame with columns corresponding to the headers listed below:
            
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

        # obtain the API response as a list of dicts
        orders_list = self.send_api_request("GET", "/orders", params=kwargs)

        # load data into df
        orders_df = self.load_df_from_API_response_list(orders_list, "id")

        if self.verbose:
            print(orders_df)

        return orders_df

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

        fees_dict = self.send_api_request("GET", "/fees")[0]

        if self.verbose:
            t.print_recursive_dict(fees_dict)

        return fees_dict

    def get_product_candles(
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
                ``time``, ``low``, ``high``, ``open``, ``close``, ``volume``
        """

        # TODO: add robust error handling

        # determine the maximum number of data points that can be pulled
        # granularity / 60 <-- get time in minutes
        # MAX_CANDLE_REQUEST -1 <-- account for fenceposting
        max_data_pull = granularity / 60 * (MAX_CANDLE_REQUEST - 1)

        # if no end is given, then use current time
        if not end:
            end = time.strftime("%Y-%m-%d %H:%M", time.localtime())

        # if no start is given, then use end minus (granularity * MAX_CANDLE_REQUEST)
        if not start:
            start = t.add_minutes_to_time_string(end, -1 * max_data_pull)

        if self.verbose:
            printed_end = min(end, t.add_minutes_to_time_string(start, max_data_pull))
            print(
                f"\n Requesting {product_id} candles from {start} to {printed_end}..."
            )

        # determine if the number of requested data points exceeds MAX_CANDLE_REQUEST
        recurse = end > t.add_minutes_to_time_string(start, max_data_pull)

        # define the actual start/end parameters which will be passed into the API request
        # NOTE: request_start is offset by 1 to get the right timestamp due to Coinbase API behavior
        request_start = t.add_minutes_to_time_string(start, -1 * granularity / 60)
        request_end = end

        # if recursion is necessary:
        # [1] modify the requested end parameter to keep it within the allowable request bounds
        # [2] update the 'start' variable to the first un-requested timestamp
        #     (this is to set up the next API request)
        if recurse:
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
            return self.get_product_candles(
                product_id, granularity, start, end, candles_df
            )

        if self.verbose:
            print()
            print(candles_df)

        return candles_df


if __name__ == "__main__":

    pass
