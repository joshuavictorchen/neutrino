import neutrino
import neutrino.tools as t
import os
import pandas as pd
from copy import deepcopy
from neutrino.datum import Datum
from neutrino.interface import Interface
from neutrino.link import Link
from neutrino.stream import Stream
from neutrino.updater import Updater
from pathlib import Path
from threading import Thread


def main():

    # start an interface
    Interface(start=True)

class Neutrino(Link):
    """Framework for performing Coinbase Pro actions. Handles :py:obj:`Streams<neutrino.stream.Stream>` (WebSocket feed messages) \
        and inherits from :py:obj:`Link<neutrino.link.Link>` (API requests/responses).

    .. note::

        Authentication is currently handled using a plaintext YAML file defined in ``user-settings.yaml``. \
        It will be updated to use a more secure method in the future.

    Args:
        cbkey_set_name (str, optional): Name of Coinbase Pro API key dictionary \
            with which the Neutrino's ``auth`` value will be initialized. Defaults to "default".

    **Instance attributes:** \n
        * **placeholder** (*placeholder*): Placeholder text. The following bullets will likely be out of date during ongoing development.
        * **database_path** (*Path*): :py:obj:`Path` object containing the absolute filepath to the folder \
            to which the Link exports CSV files.
        * **accounts** (*dict*): Dictionary representation of DataFrame returned from :py:obj:`Link.retrieve_accounts`.
        * **ledgers** (*dict(dict)*): Nested dictionary representations of DataFrames returned from :py:obj:`Link.retrieve_account_ledger`, \
            with one entry per retrieved ``account_id`` in the form of ``{account_id: {ledger_dict}}``.
        * **transfers** (*dict*): Dictionary representation of DataFrame returned from :py:obj:`Link.get_usd_transfers`.
        * **orders** (*dict*): Dictionary representation of DataFrame returned from :py:obj:`Link.retrieve_orders`.
        * **fees** (*dict*): Dictionary of Coinbase fee data returned from :py:obj:`Link.retrieve_fees`.
        * **coins** (*dict*): To be implemented - dict for each coin containing account info, orders, transfers.
    """

    def __init__(self, cbkey_set_name="default", from_database=False, verbose=True):

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

        # temporary measure for testing:
        # if keys_file does not exist, update keys file to sanbox test keys
        sandbox = False
        if not os.path.isfile(self.user_settings.get("keys_file")):
            sandbox = True
            self.user_settings["keys_file"] = (
                self.neutrino_dir / "tests/sandbox-keys.yaml"
            )

        # load dictionary of cbkey dicts
        # TODO: don't store secrets in an attribute like this
        self.cbkeys = t.parse_yaml(self.user_settings.get("keys_file"), echo_yaml=False)

        # define database path
        self.database_path = self.neutrino_dir / "database"  # CSV database path

        # initialize inherited Link parameters
        super().__init__(
            self.cbkeys.get(cbkey_set_name),  # cbkey dictionary
        )

        # check for updates, if specified by user settings entry
        self.updater = Updater(check=self.user_settings.get("check_for_updates"))

        # establish unique neutrino attributes
        self.verbose = verbose
        self.streams = {}
        self.threads = {}
        self.coins = {}

        # load data
        if not sandbox:
            self.load_all_data(from_database=from_database)

    def refresh_user_settings(self):
        """Reloads ``self.user_settings`` from ``self.user_settings_file``. This allows the user to update the \
            user settings file with different inputs between Neutrino commands.
        """

        self.user_settings = t.load_yaml_settings(
            self.user_settings_file, self.template_user_settings_file
        )

    def set_verbosity(self, verbose):
        """Updates Neutrino's behavior to print (or not print) responses to the console.

        Args:
            verbose (bool): ``True`` if print statements are desired.
        """

        self.verbose = verbose

        # print settings change to console
        verb = "will" if verbose else "won't"
        print(f"\n Responses {verb} be printed to the console.")

    def generate_datum(
        self, name, from_database, method="get", endpoint=None, save=False, **kwargs
    ):

        api_request = True
        db_file = neutrino.db_path / (name + ".csv")
        main_key = neutrino.api_response_keys.get(name)

        if endpoint is None:
            endpoint = f"/{name}"

        if from_database:
            if os.path.isfile(db_file):
                df = pd.read_csv(db_file)
                origin = "db"
                api_request = False
            else:
                print(
                    f"\n NOTE: {db_file} does not exist.\n\n Data will be pulled via API request."
                )

        if api_request:
            df = self.convert_API_response_list_to_df(
                self.send_api_request(method, endpoint, params=kwargs), main_key
            )
            origin = "api"

        df = t.clean_df_timestrings(df)

        return Datum(name, df, main_key, origin, save)

    def load_all_data(self, from_database):

        data_source = neutrino.db_path if from_database else neutrino.api_url
        print(f"\n Forming neutrino via: {data_source}")

        self.accounts = self.generate_datum(
            name="accounts", from_database=from_database
        )

        self.ledgers = None  # TBD

        # ledgers = {}
        # for i in account_df.index:
        #     ledgers[i] = self.get_account_ledger(account_df.at[i, "id"])

        self.transfers = self.generate_datum(
            name="transfers", from_database=from_database
        )

        self.orders = self.generate_datum(
            name="orders", from_database=from_database, status="all"
        )

        self.fees = self.send_api_request("GET", "/fees")[0]

    ###########################################################################
    # get methods
    ###########################################################################

    def filter_accounts(
        self, account_df, relevant_only=True, exclude_empty_accounts=False
    ):
        """Loads a DataFrame with all relevant trading accounts and their holdings for the authenticated profile.

        Args:
            relevant_only (bool, optional): The API retuns all accounts for all available coins by default. \
                Set this to ``True`` to only include accounts that have seen activity in the past in the returned result.
            exclude_empty_accounts (bool, optional): The API retuns all accounts for all available coins by default. \
                Set this to ``True`` to exclude zero-balance accounts from the returned result.
            from_database (bool, optional): Loads from the local CSV database if ``True``. Otherwise, performs an API request for fresh data. Defaults to ``False``.
            save (bool, optional): Exports the returned DataFrame to a CSV file in the directory specified by ``self.database_path`` if ``True``. Defaults to ``False``.
        
        Returns:
            DataFrame: DataFrame with the following columns:
            
                * to be completed
                * at a later date
        """

        df = deepcopy(account_df)

        # filter to only accounts that have had some activity at any point in time, if applicable
        # use order history to get list of currencies where activity has been seen
        if relevant_only:
            currencies = (
                self.orders.df["product_id"]
                .apply(lambda x: x.split("-")[0])
                .unique()
                .tolist()
            )
            df = self.accounts.df[
                self.accounts.df["currency"].isin(currencies)
            ].reset_index(drop=True)

        # exclude accounts with <= 0 balance, if applicable
        if exclude_empty_accounts:
            df = df[df["balance"].astype(float) > 0].reset_index(drop=True)

        if self.verbose:
            print()
            print(df)

        return df

    def get_account_ledger(self, account_id, from_database=False, save=False, **kwargs):

        # change to "get ledgers"

        account_ledger = self.generate_datum(
            name="ledger",
            from_database=from_database,
            endpoint=f"/accounts/{account_id}/ledger",
            **kwargs,
        )

        if save:
            account_ledger.save_csv(
                f"ledger-{self.accounts.get('currency', account_id)}"
            )

        return account_ledger

    ###########################################################################
    # candle methods
    ###########################################################################

    def get_product_candles(
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

        if self.verbose:
            print()
            print(returned_df)

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
                " \n Database values will be augmented with the following Link requests:"
            )
            t.print_recursive_dict(pull_bounds)

        return pull_bounds

    def retrieve_ledgers(self, currencies, save=False):

        pass

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


if __name__ == "__main__":

    main()
