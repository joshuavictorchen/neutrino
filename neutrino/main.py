import neutrino
import neutrino.tools as t
import os
import pandas as pd
import time
import traceback
from copy import deepcopy
from datetime import datetime
from neutrino.datum import Datum
from neutrino.link import Link
from neutrino.stream import Stream
from neutrino.updater import Updater
from pathlib import Path
from threading import Thread


def main():

    # instantiate a Neutrino
    n = Neutrino(cbkey_set_name="default", from_database=True)

    # start interacting
    n.interact()


class Neutrino(Link):
    """Framework for performing Coinbase Pro actions. Handles :py:obj:`Streams<neutrino.stream.Stream>` (WebSocket feed messages) \
        and inherits from :py:obj:`Link<neutrino.link.Link>` (API requests/responses).

    .. note::

        Authentication is currently handled using a plaintext YAML file defined in ``user-settings.yaml``. \
        It will be updated to use a more secure method in the future.

    .. admonition:: TODO

        More detailed docs to be completed.

    Args:
        cbkey_set_name (str, optional): Name of Coinbase Pro API key dictionary \
            with which the Neutrino's ``auth`` value will be initialized. Defaults to "default".

    **Relevant instance attributes:** \n
        * **user_settings** (*dict*): Dictionary of user settings parameters from ``neutrino\\user-settings.yaml``.
        * **updater** (*Updater*): Updater object containing neutrino repo attributes and update methods.
        * **cbkeys** (*dict*): Dictionary of Coinbase Pro API keys from the YAML file specified in ``user_settings``.
        * **database_path** (*Path*): :py:obj:`Path` containing the absolute filepath to the CSV file directory.
        * **auth** (*Authenticator*): Callable :py:obj:`Authenticator` for Coinbase WebSocket and API authentication.
        * **session** (*Session*): :py:obj:`requests.Session` for API requests.
        * **streams** (*dict*): Dictionary of :py:obj:`Stream` objects for live streams of WebSocket feed data.
        * **threads** (*dict*): Dictionary of :py:obj:`Thread` objects corresponding :py:obj:`Stream` objects.
        * **accounts** (*Datum*): :py:obj:`Datum` of data from the Coinbase Pro API "accounts" endpoint.
        * **ledgers** (*Datum*): :py:obj:`Datum` of consolidated ledger entries associated with all :py:obj:`self.accounts`.
        * **transfers** (*Datum*): :py:obj:`Datum` of data from the Coinbase Pro API "transfers" endpoint.
        * **orders** (*Datum*): :py:obj:`Datum` of data from the Coinbase Pro API "orders" endpoint.
        * **fees** (*dict*): Dictionary of trailing 30 day USD volume, maker fee rate, and taker fee rate.
        * **coins** (*dict*): To be implemented - dict for each coin containing account info, orders, transfers.
    """

    def __init__(self, cbkey_set_name="default", from_database=False, save=False):

        # establish directory in which neutrino is installed
        self.neutrino_dir = Path(
            os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
        )

        # load user settings
        self.user_settings_file = self.neutrino_dir / "user-settings.yaml"
        self.template_user_settings_file = (
            self.neutrino_dir / "internals/template-user-settings.yaml"
        )
        self.user_settings = t.load_yaml_settings(
            self.user_settings_file, self.template_user_settings_file
        )

        # NOTE: the sandbox variable is a temporary workaround to get GitHub test builds to work
        #       until actual unit tests are implemented
        #       for now, it's set to True (i.e., don't perform certain actions) if no valid cbkeys file is provided
        sandbox = False

        # temporary measure for testing:
        # if keys_file does not exist, update keys file to sandbox test keys
        if not os.path.isfile(self.user_settings.get("keys_file")):
            sandbox = True
            self.user_settings["keys_file"] = (
                self.neutrino_dir / "tests/sandbox-keys.yaml"
            )

        # check for updates, if specified by user settings entry
        if not sandbox:
            self.updater = Updater(check=self.user_settings.get("check_for_updates"))

        # load dictionary of cbkey dicts
        # TODO: don't store secrets in an attribute like this
        self.cbkeys = t.parse_yaml(self.user_settings.get("keys_file"), echo_yaml=False)

        # define database path
        self.database_path = self.neutrino_dir / "database"  # CSV database path

        # create database dir if one doesn't already exist
        if not os.path.isdir(self.database_path):
            print(f"\n Initializing database directory: {self.database_path}")
            os.mkdir(self.database_path)

        # initialize inherited Link parameters
        super().__init__(
            self.cbkeys.get(cbkey_set_name),  # cbkey dictionary
        )

        # establish unique neutrino attributes
        self.streams = {}
        self.threads = {}
        self.coins = {}

        # load initial data sets
        if not sandbox:

            # choose the data source from neutrino module attributes
            data_source = neutrino.db_path if from_database else neutrino.api_url
            print(f"\n Forming neutrino via: {data_source}")

            # get accounts Datum from the accounts endpoint (or corresponding database CSV)
            self.accounts = self.load_datum(
                name="accounts", from_database=from_database, save=save
            )

            # get transfers Datum from the transfers endpoint
            self.transfers = self.load_datum(
                name="transfers", from_database=from_database, save=save
            )

            # get orders Datum from the orders endpoint
            self.orders = self.load_datum(
                name="orders", from_database=from_database, save=save, status="all"
            )

            # get ledgers Datum from the accounts/{account_id}/ledger endpoint (via the load_ledgers function)
            self.ledgers = self.load_ledgers(
                self.accounts, self.orders.df, from_database=from_database, save=save
            )

            # commented out for now - get fees at runtime as needed
            # get fees dictionary from the fees endpoint (note: this is just a dictionary of volume and maker/taker rates)
            # TODO: make fees db file and pull from it as applicable
            # self.fees = self.send_api_request("get", "fees")[0]

    def refresh_user_settings(self):
        """Reloads ``self.user_settings`` from ``self.user_settings_file``. This allows the user to update the \
            user settings file with different inputs between Neutrino commands.
        """

        self.user_settings = t.load_yaml_settings(
            self.user_settings_file, self.template_user_settings_file
        )

    ###########################################################################
    # datum handling and loading
    ###########################################################################

    def load_datum(
        self,
        name,
        from_database,
        method="get",
        endpoint=None,
        main_key=None,
        save=False,
        **kwargs,
    ):
        """Generates a :py:obj:`Datum<neutrino.datum.Datum>` object corresponding to a Coinbase API endpoint.

        More thorough documentation TBD.

        .. admonition:: TODO

            Update program structure for more generalized Datum loading, and/or add checks to ensure the Datum is valid.

        Args:
            name (str): Name of the :py:obj:`Datum` to be loaded.
            from_database (bool): Loads data from the local database if ``True``, otherwise requests fresh \
                Coinbase API pulls.
            method (str, optional): API request method (``get``, ``post``, etc.). Defaults to "get".
            endpoint (str, optional): API request endpoint, with no leading ``/`` (i.e., "accounts"). Defaults to the provided ``name``.
            save (bool, optional): Exports the DataFrame's data as a CSV to the default database path if ``True``. Defaults to ``False``.

        Returns:
            Datum: Datum object corresponding to the requested name and/or Coinbase API endpoint.
        """

        # get the Datum's main key from neutrino module attributes, if not already provided
        main_key = neutrino.api_response_keys.get(name) if not main_key else main_key

        if not main_key:
            raise ValueError(
                f"\n ERROR: main key not found for {name} while generating Datum."
            )

        # if no enpoint is explicitly defined, then default to using the Datum's name as the endpoint
        # TODO: make a maintained list of acceptable endpoints for error checking
        if endpoint is None:
            endpoint = f"{name}"

        # load df data from CSV database, if applicable
        if from_database:
            db_file = neutrino.db_path / (name + ".csv")
            if os.path.isfile(db_file):
                df = pd.read_csv(db_file)
            # if no database file exists, then default to performing a fresh API request
            # set from_database to false to ensure this happens
            else:
                from_database = False
                print(
                    f"\n NOTE: {db_file} does not exist.\
                    \n       {name} data will be pulled via API request."
                )

        # perform a fresh API request for df data, if a database pull was not performed
        if not from_database:
            df = self.convert_API_response_list_to_df(
                self.send_api_request(method, endpoint, params=kwargs), main_key
            )

        # clean the df's time strings
        df = t.clean_df_timestrings(df)

        # return an instantiated a Datum object with the df and its metadata
        return Datum(name, df, main_key, save)

    def filter_accounts(
        self, account_df, orders_df, relevant_only=True, exclude_empty_accounts=False
    ):
        """Filters a DataFrame of account information per the supplied arguments and returns the result.

        .. admonition:: TODO

            1. Ensure ``account_df`` is actually a DataFrame of account info.
            2. Ensure ``orders_df`` is actually a DataFrame of orders info. 
            3. Handle potential non-existence of :py:obj:`self.orders` prior to performing actions.

        Args:
            account_df (DataFrame): DataFrame of account data as pulled from the Coinbase API.
            orders_df (DataFrame): DataFrame of orders data as pulled from the Coinbase API.
            relevant_only (bool, optional): Only includes accounts that have seen activity in the past \
                if ``True``, using data from ``orders_df`` to gauge activity. Defaults to ``True``.
            exclude_empty_accounts (bool, optional): Excludes currently-zero-balanced accounts \
                from the returned result if ``True``. Defaults to ``False``.
        
        Returns:
            DataFrame: Filtered DataFrame of account information.
        """

        df = deepcopy(account_df)

        # filter to only accounts that have had some activity at any point in time, if applicable
        # use order history to get list of currencies where activity has been seen
        if relevant_only:
            currencies = (
                orders_df["product_id"]
                .apply(lambda x: x.split("-")[0])  # TODO: consider [1] as well
                .unique()
                .tolist()
            )
            df = df[df["currency"].isin(currencies)].reset_index(drop=True)

        # exclude accounts with <= 0 balance, if applicable
        if exclude_empty_accounts:
            df = df[df["balance"].astype(float) > 0].reset_index(drop=True)

        return df

    def load_ledgers(
        self, account_datum, orders_df, from_database=False, save=False, **kwargs
    ):
        """Pulls the ledgers for all relevant accounts loaded in :py:obj:`self.accounts` and consolidates the data into \
            one Datum.

            More information on ledger data can be found on the `API reference page <https://docs.cloud.coinbase.com/exchange/reference/exchangerestapi_getaccountledger>`__.

            More detailed documentation TBD.

        .. admonition:: TODO

            If loading from the local database, perform API requests for missing accounts and orders, if any exist.

        Args:
            account_datum (Datum): Datum of account data as pulled from the Coinbase API.
            orders_df (DataFrame): DataFrame of orders data as pulled from the Coinbase API.
            from_database (bool, optional): Loads from the local CSV database if ``True``. Otherwise, performs an API request for fresh data. Defaults to ``False``.
            save (bool, optional): Exports the returned DataFrame to a CSV file in the directory specified by ``self.database_path`` if ``True``. Defaults to ``False``.

        Returns:
            Datum: Datum of consolidated ledger entries associated with all :py:obj:`self.accounts`.
        """

        # pull data from database, if applicable
        # if no local ledgers data exists, then default to pulling via API request
        if from_database:
            db_file = neutrino.db_path / "ledgers.csv"
            if os.path.isfile(db_file):
                ledgers_df = pd.read_csv(db_file)
            else:
                # set from_database to False to force an API pull
                from_database = False
                print(
                    f"\n NOTE: {db_file} does not exist.\
                    \n       Ledger data will be pulled via API request."
                )

        # if data was not pulled from the database, then pull via API request
        if not from_database:

            # get a list of relevant accounts (accounts with any historical activity)
            accounts_df = self.filter_accounts(account_datum.df, orders_df)

            # create empty ledgers_df and append ledger pulls for each account in accounts_df
            ledgers_df = pd.DataFrame()

            for i in accounts_df.index:
                account_id = accounts_df.at[i, "id"]
                currency = account_datum.get("currency", account_id)
                this_ledger = self.load_datum(
                    name="ledger",
                    from_database=from_database,
                    endpoint=f"accounts/{account_id}/ledger",
                    save=False,
                    **kwargs,
                ).df

                # store the currency of the account for which the ledger is being pulled
                # this is important because some product_ids contain two currencies (i.e. "LRC-BTC"),
                # but from different currency perspectives (i.e., one with LRC denomination and one with BTC)
                this_ledger["currency"] = currency

                ledgers_df = ledgers_df.append(this_ledger, ignore_index=True)

        # clean indices and time strings
        ledgers_df.reset_index(drop=True, inplace=True)
        ledgers_df = t.clean_df_timestrings(ledgers_df)

        # create ledgers Datum and store in self.ledgers
        self.ledgers = Datum("ledgers", ledgers_df, "id", save=save)

        return self.ledgers

    # The following is a legacy function that is left as a comment for potential future use.
    #
    # It is an artefact of the original direction of the neutrino program, which sought to
    # provide functions for each API endpoint, similar to the existing cbpro-python package.
    #
    # def get_account_ledger(self, account_id, from_database=False, save=False, **kwargs):
    #
    #     account_ledger = self.generate_datum(
    #         name="ledger",
    #         from_database=from_database,
    #         endpoint=f"accounts/{account_id}/ledger",
    #         **kwargs,
    #     )
    #
    #     if save:
    #         account_ledger.save_csv(
    #             f"ledger-{self.accounts.get('currency', account_id)}"
    #         )
    #
    #     return account_ledger

    ###########################################################################
    # candle methods
    ###########################################################################

    def load_product_candles(
        self, product_id, granularity=60, start=None, end=None, save=False
    ):
        """Performs the following actions to efficiently retrieve the requested product candle dataset:

            1. Loads in a dataframe of ``product_id`` data from the Neutrino's ``database`` directory, if \
                such data exists.
            2. Inspects the dataframe from Step 1 (if applicable) and augments this data as necessary via \
                new API requests.
            3. Saves the augmented data to the ``database`` file, if applicable.
            4. Returns a DataFrame of ``product_id`` candles with the appropriate ``start`` and ``end`` bounds.

        Args:
            product_id (str): The coin trading pair (i.e., 'BTC-USD').
            granularity (int, optional): Granularity of the returned candles in seconds. Must be one of the following values: \
                ``60``, ``300``, ``900``, ``3600``, ``21600``, ``86400``.
            start (str, optional): Start bound of the request (``%Y-%m-%d %H:%M``).
            end (str, optional): End bound of the request (``%Y-%m-%d %H:%M``).
            save (bool, optional): Exports the augmented dataset to the ``database`` file if ``True``. \
                Defaults to ``False``.

        Returns:
            DataFrame: DataFrame with the following columns for each candle: \
                ``time``, ``product_id``, ``low``, ``high``, ``open``, ``close``, ``volume``
        """

        # update start/end bounds if no input was provided
        (start, end) = self.augment_candle_bounds(
            self.calculate_max_candle_pull_minutes(granularity), start, end
        )

        # establish name of the associated database CSV file for the given parameters
        csv_name = f"candles-{granularity}-{product_id}"
        csv_file = csv_name + ".csv"

        # if dbfile exists, then load the existing database data and combine w/ newly pulled data as necessary
        if os.path.isfile(self.database_path / csv_file):

            # load data from database
            candles_df = t.clean_df_timestrings(
                pd.read_csv(self.database_path / csv_file)
            )

            # generate dict of start: end time pairs to pull, if database_df does not cover the requested data
            pull_bounds = self.generate_candle_pull_bounds(
                candles_df, granularity, start, end
            )

            # loop through the list of pull bounds and augment database_df
            for pull_start, pull_end in pull_bounds.items():
                pulled_df = self.retrieve_product_candles(
                    product_id, granularity, pull_start, pull_end
                )
                candles_df = candles_df.append(pulled_df, ignore_index=True)

            # sort candles_df
            candles_df = candles_df.sort_values(
                by=["time"], ascending=True
            ).reset_index(drop=True)

        # if dbfile doesn't exist, then just pull the candle data
        else:
            candles_df = self.retrieve_product_candles(
                product_id, granularity, start, end
            )

        # trim candles_df to the requested bounds
        returned_df = candles_df[
            (candles_df["time"] >= start) & (candles_df["time"] <= end)
        ].reset_index(drop=True)

        # save to CSV, if applicable
        if save:
            returned_df = t.save_df_to_csv(candles_df, csv_name, self.database_path)

        return returned_df

    def generate_candle_pull_bounds(self, candles_df, granularity, start, end):
        """Determines what additional API requests need to be made, if any, to augment a provided dataset \
            in order to fulfill a request for candle data.

            This function looks for required pulls:

                1. Before the first ``candles_df`` entry.
                2. After the last ``candles_df`` entry.
                3. Within the ``candles_df`` entry for an arbitrary amount of internal gaps in the dataset.

        Args:
            candles_df (DataFrame): Initial dataset of candle data for a given ``product_id``.
            granularity (int, optional): Granularity of the returned candles in seconds. Must be one of the following values: \
                ``60``, ``300``, ``900``, ``3600``, ``21600``, ``86400``.
            start (str, optional): Start bound of the request (``%Y-%m-%d %H:%M``).
            end (str, optional): End bound of the request (``%Y-%m-%d %H:%M``).

        Returns:
            dict (str): Dictionary of required pull bounds in the following form:

            .. code-block::

                {
                    start_time_1: end_time_1,
                    start_time_2: end_time_2,
                    ...
                    start_time_n: end_time_n
                }
        """

        pull_bounds = {}

        # get pull bounds for requested data BEFORE the FIRST value in candles_df
        # this goes from 'start' to the minimum of the first candles_df value minus one time step, and the requested end time
        if start < candles_df["time"].min():
            this_end = min(
                t.add_minutes_to_time_string(
                    candles_df["time"].min(), -1 * granularity / 60
                ),
                end,
            )
            pull_bounds.update({start: this_end})

        # get pull bounds for requested data AFTER the LAST value in candles_df
        # this goes from the maximum of the last candles_df value plus one time step, and the requested start time
        if end > candles_df["time"].max():
            this_start = max(
                t.add_minutes_to_time_string(
                    candles_df["time"].max(), granularity / 60
                ),
                start,
            )
            pull_bounds.update({this_start: end})

        # get pull bounds for any 'gaps' in the existing candles_df data

        # create a dataframe with one column each for:
        #   candles_df["time"] plus one minute
        #   candles_df["time"] with each element shifted up one row
        gap_df = pd.DataFrame()
        gap_df["start"] = candles_df["time"].apply(
            lambda x: t.add_minutes_to_time_string(x, 1)
        )
        gap_df["end"] = candles_df.time.shift(-1)

        # any rows in this dataframe where those two columns don't match up signify gaps in candles_df
        gap_df = gap_df[
            (gap_df["start"] != gap_df["end"]) & gap_df["end"].notna()
        ].reset_index(drop=True)

        # subtract one minute from each element of the latter column to produce a dataframe of required start/end bounds
        gap_df["end"] = gap_df["end"].apply(
            lambda x: t.add_minutes_to_time_string(x, -1)
        )

        # update dict of pull bounds with this data
        for i in gap_df.index:
            pull_bounds.update({gap_df.at[i, "start"]: gap_df.at[i, "end"]})

        if len(pull_bounds) > 0:
            print(
                " \n Database values will be augmented with the following pull bound(s):"
            )
            t.print_recursive_dict(pull_bounds)

        return pull_bounds

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

        # determine if the number of requested data points exceeds neutrino.MAX_CANDLE_REQUEST
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
            "get", f"products/{product_id}/candles", params=params_dict
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
        # neutrino.MAX_CANDLE_REQUEST -1 <-- account for fenceposting

        return granularity / 60 * (neutrino.MAX_CANDLE_REQUEST - 1)

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

    ###########################################################################
    # stream methods
    ###########################################################################

    def configure_new_stream(
        self, name, product_ids, channels, type="subscribe", cbkey_set_name="default"
    ):
        """Instantiates and configures a new :py:obj:`Stream<neutrino.stream.Stream>` object.

        Updates ``self.streams`` and ``self.threads`` with this object and corresponding thread.

        Args:
            name (str): User-specified name of the new :py:obj:`Stream<neutrino.stream.Stream>` object.
            product_ids (list(str)): List of coin trading pairs (i.e., ['BTC-USD']).
            channels (list(str)): List of channels specified for the WebSocket connection (i.e., ['ticker']).
            type (str): Type of message that is sent to the WebSocket endpoint upon opening a connection. Defaults to "subscribe".
            cbkey_set_name (str, optional): Name of the ``cbkey_set`` dictionary defined in the cbkeys file. Defaults to "default".

        Raises:
            ValueError: If the specified stream name already exists.
        """

        # notify user that configuration is being overwritten, if applicable
        if name in self.streams:
            print(f"\n Overwriting configuration for stream: {name}")

        # TODO: error handling and reqs checking for arguments

        # get keys for authentication - default is the 'default' key name; if no key is provided, then None is passed (no auth)
        auth_keys = self.cbkeys.get(cbkey_set_name)

        # initialize a stream + thread, and add to self.streams and self.threads
        stream = Stream(
            name,
            type,
            product_ids,
            channels,
            auth_keys,
        )
        thread = Thread(target=stream.stream, name=name)
        self.streams[name] = stream
        self.threads[name] = thread

        print(f"\n Stream {name} configured:\n")
        print(f"       type: {type}")
        print(f"   products: {product_ids}")
        print(f"   channels: {channels}")

    def start_stream(self, stream_name):
        """Starts the thread for a configured Coinbase WebSocket :py:obj:`Stream<neutrino.stream.Stream>`.

        Args:
            stream_name (str): Name of the configured Coinbase WebSocket :py:obj:`Stream<neutrino.stream.Stream>` to be started.
        """

        # don't start the stream if it has already previously been run
        if not self.streams.get(stream_name).killed:
            self.threads.get(stream_name).start()
        else:
            raise Exception(
                f"\n Cannot revive a dead stream - please reconfigure this stream or start a new one."
            )

    def stop_stream(self, stream_name):
        """Closes a configured Coinbase WebSocket :py:obj:`Stream<neutrino.stream.Stream>` and stops its Thread.

        Args:
            stream_name (str): Name of the configured Coinbase WebSocket :py:obj:`Stream<neutrino.stream.Stream>` to be stopped.
        """

        # perform close-out actions for the Stream object
        self.streams.get(stream_name).kill()

        # join the existing Thread
        self.threads.get(stream_name).join()

    def parse_stream_messages(self, stream_name):
        """Test function to parse :py:obj:`Stream<neutrino.stream.Stream>` messages.

        Args:
            stream_name (string): Name of :py:obj:`Stream<neutrino.stream.Stream>` whom's messages to parse.
        """

        parsed_message_count = 0
        while True:
            # get streamed data, which is a tuple of the form: (message count, message)
            stream_data = self.streams.get(stream_name).latest_message

            # skip to next iteration if no data is present, or if the most recent data has already been parsed
            if not stream_data or parsed_message_count == stream_data[0]:
                continue

            parsed_message_count += 1
            # print(f"-- streamed: {stream_data[0]} | parsed: {parsed_message_count} --")

            # perform actions based on message type
            message = stream_data[1]
            dtype = message.get("type")
            if dtype == "ticker":
                self.handle_ticker_message(message)
            elif dtype == "error":
                print(" error encountered - stream will be closed:\n")
                t.print_recursive_dict(message)
                self.streams.get(stream_name).kill()
            else:
                # TODO: handle other items
                t.print_recursive_dict(message)
                print()

    def handle_ticker_message(self, message):
        """Temporary test actions taken upon receipt of a Coinbase WebSocket ticker message from a :py:obj:`Stream<neutrino.stream.Stream>`.

        Args:
            message (dict): Placeholder, TBD.
        """

        ticker_product = message.get("product_id")

        # store new data and determine if price increased or decreased since last tick for this product
        prev_tick = self.coins.get(ticker_product)
        if prev_tick is not None:
            prev_price = prev_tick.get("ticker").get("price")
            self.coins.get(ticker_product)["ticker"] = message
            if message.get("price") > prev_price:
                pdelta = "↑"
            elif message.get("price") < prev_price:
                pdelta = "↓"
            else:
                pdelta = "→"
        else:
            self.coins.update({ticker_product: {"ticker": message}})
            pdelta = "→"

        # output data to console
        print(
            " "
            + t.ISO_to_local_time_string(message.get("time"), "%Y-%m-%d %H:%M:%S")
            + f' | {ticker_product} {pdelta} | {message.get("price")}'
        )

    ###########################################################################
    # temporary 'client' methods
    ###########################################################################

    def interact(self):
        """Temporary rudimentary command line interface that executes neutrino-related commands from user input. \
        The jankiness of this implementation and availability of modules such as ``argparse`` are well-understood. \
        This is mostly used for flexible testing/debugging during development.

        The actions here are mainly loading/exporting data in various chunks, whereas the real actions of this \
        program are intended to be focused around data analysis and manipulation.

        This function is wrapped in a ``while True`` block to execute an arbitrary number of commands \
        until terminated by the user.
        """

        # continuously accept user input
        while True:

            try:

                print(neutrino.DIVIDER)

                # gather user input as a list of tokens
                arg = input("\n>>> ").split()

                # reload user settings (user can update settings file prior to providing a new command)
                self.refresh_user_settings()

                # don't do anything if no input was provided
                if len(arg) == 0:
                    continue

                # TODO: get arg metadata (length, etc.)

                # exit the program if 'quit' or 'q' are entered
                if arg[0] in ("quit", "q"):
                    break

                # print list of available commands
                if arg[0] in ("help", "h"):
                    print(
                        "\n A printed list of available commands. Not yet implemented."
                    )

                # print n attributes/internal data
                if arg[0] in ("state"):
                    print(
                        "\n A summary of the Neutrino's Datum objects. Not yet implemented."
                    )

                # update cbkey_set_name used for authentication
                elif arg[0] == "cbkeys":

                    if len(arg) == 1:
                        print(
                            f"\n No keys provided. Please provide a value for cbkey_set_name."
                        )

                    # list the available cbkey names
                    elif arg[-1] == "-l":
                        print("\n Available API key sets:")
                        [print(f"   + {i}") for i in self.cbkeys.keys()]

                    else:
                        self.update_auth(self.cbkeys.get(arg[1]))
                        print(f"\n API key set changed to: {arg[1]}")

                # parse 'get' statements
                elif arg[0] == "get":

                    # establish whether or not to export retrieved data to CSV,
                    # or whether or not to load data from CSV
                    save = True if arg[-1] == "-s" else False
                    from_database = True if arg[-1] == "-d" else False

                    # TODO: prompt user w/ list of acceptable values
                    if len(arg) == 1:
                        print(
                            f"\n No 'get' method provided. Please specify what should be retrieved."
                        )

                    elif arg[1] == "accounts":

                        # get account data
                        accounts = self.load_datum(
                            name="accounts",
                            from_database=from_database,
                        )

                        # filter to default filter_accounts filters if 'all' was not specified
                        if len(arg) <= 2 or arg[2] != "all":
                            accounts.df = self.filter_accounts(
                                accounts.df, self.orders.df
                            )

                        if save:
                            accounts.save_csv()

                        accounts.print_df()

                    elif arg[1] == "ledger":

                        # parse which currency for which to get the ledger - default to BTC if none given
                        if len(arg) > 2:
                            currency = arg[2]
                        else:
                            print("\n No currency provided - using BTC as default:")
                            currency = "BTC"

                        self.load_datum(
                            name="ledger",
                            from_database=from_database,
                            endpoint=f"accounts/{self.accounts.get('id', currency, 'currency')}/ledger",
                            save=save,
                        ).print_df()

                    elif arg[1] == "ledgers":

                        self.load_ledgers(
                            self.accounts,
                            self.orders.df,
                            from_database=from_database,
                            save=save,
                        ).print_df()

                    elif arg[1] == "transfers":

                        self.load_datum(
                            name="transfers", from_database=from_database, save=save
                        ).print_df()

                    elif arg[1] == "orders":

                        # get the list of requested statuses from args
                        status = [i for i in arg[2:] if i not in ("-s", "-d")]

                        # if no statuses are requested, then default to 'all'
                        status = "all" if status == [] else status

                        self.load_datum(
                            name="orders",
                            from_database=from_database,
                            save=save,
                            status=status,
                        ).print_df()

                    elif arg[1] == "fees":
                        t.print_recursive_dict(self.send_api_request("get", "fees")[0])

                    elif arg[1] == "candles":
                        candles_df = self.load_product_candles(
                            self.user_settings.get("candles").get("product_id"),
                            granularity=self.user_settings.get("candles").get(
                                "granularity"
                            ),
                            start=self.user_settings.get("candles").get("start"),
                            end=self.user_settings.get("candles").get("end"),
                            save=save,
                        )
                        print()
                        print(candles_df)

                    elif arg[1] == "all":
                        print("\n TBD")

                    else:  # generic API/database request

                        self.load_datum(
                            name=arg[1],
                            from_database=from_database,
                            method="get",
                            endpoint=f"{arg[1]}",
                            save=save,
                        ).print_df()

                # stream data
                elif arg[0] == "stream":

                    # TODO: prompt user w/ list of acceptable values
                    if len(arg) < 2:
                        print(
                            f"\n Stream name not specified. Please specify a stream name."
                        )

                    # partially hard-code for now - in future, split into components, let user append items to lists, etc.
                    self.configure_new_stream(
                        arg[1],
                        self.user_settings.get("stream").get("product_ids"),
                        self.user_settings.get("stream").get("channels"),
                    )

                    try:
                        self.start_stream(arg[1])
                        self.parse_stream_messages(arg[1])
                    # TODO: implement a cleaner way to kill a stream
                    except KeyboardInterrupt:
                        self.stop_stream(arg[1])
                    # TODO: implement specific errors
                    except Exception as e:
                        if self.streams.get(arg[1]).active:
                            self.stop_stream(arg[1])
                        print(f"\n {e}")

                elif arg[0] == "update":

                    if arg[-1] == "-f":
                        self.updater.update_neutrino(force=True)
                    else:
                        self.updater.check_for_updates()

                else:
                    print("\n Unrecognized command or specification.")

            except Exception as exc:
                if exc == "\n Neutrino annihilated.":
                    break
                else:
                    print(
                        "\n ERROR: prototype interface has encountered the following exception:\n"
                    )
                    [print(f"   {i}") for i in traceback.format_exc().split("\n")]

        print("\n Neutrino annihilated.")
        print(neutrino.DIVIDER)


if __name__ == "__main__":

    main()
