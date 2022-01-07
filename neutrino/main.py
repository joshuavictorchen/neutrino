import neutrino.tools as t
import os
import pandas as pd
import subprocess
import sys
import traceback
from neutrino.datum import Datum
from neutrino.link import Link
from neutrino.stream import Stream
from pathlib import Path
from threading import Thread

DIVIDER = (
    "\n -------------------------------------------------------------------------------"
)


def main():

    # print repository data
    t.retrieve_repo(verbose=True)

    # instantiate a Neutrino
    # hard-code 'default' cbkey_set_name for now
    # TODO: make this an input parameter and/or echo list of default values
    n = Neutrino("default")

    # perform actions
    n.interact()

    # exit program
    print("\n Neutrino annihilated.")
    print(DIVIDER)


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

    def __init__(self, cbkey_set_name="default", verbose=True):

        # establish directory in which neutrino is installed
        self.neutrino_dir = Path(
            os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
        )

        # load neutrino settings
        self.neutrino_settings = t.parse_yaml(
            self.neutrino_dir / "strings/neutrino-settings.yaml", echo_yaml=False
        )

        # load user settings
        self.user_settings_file = self.neutrino_dir / "user-settings.yaml"
        self.template_user_settings_file = (
            self.neutrino_dir / "strings/template-user-settings.yaml"
        )
        self.user_settings = t.load_yaml_settings(
            self.user_settings_file, self.template_user_settings_file
        )

        # temporary measure for testing:
        # if keys_file does not exist, update keys file to sanbox test keys
        if not os.path.isfile(self.user_settings.get("keys_file")):
            self.user_settings["keys_file"] = (
                self.neutrino_dir / "tests/sandbox-keys.yaml"
            )

        # load dictionary of cbkey dicts
        self.cbkeys = t.parse_yaml(self.user_settings.get("keys_file"), echo_yaml=False)

        # define database path
        self.database_path = self.neutrino_dir / "database"  # CSV database path

        # initialize inherited Link parameters
        super().__init__(
            self.neutrino_settings.get("api_url"),  # API endoint base url
            self.cbkeys.get(cbkey_set_name),  # cbkey dictionary
        )

        # check for updates
        self.repo = t.retrieve_repo()
        if self.user_settings.get("check_for_updates"):
            self.check_for_updates()

        # establish unique neutrino attributes
        self.verbose = verbose
        self.accounts = None
        self.ledgers = None
        self.transfers = None
        self.orders = None
        self.fees = {}
        self.streams = {}
        self.threads = {}
        self.coins = {}

    def check_for_updates(self):
        """Performs a ``git fetch`` command to check for updates to the current branch of the repository.

        If updates exist, then prompts the user to execute :py:obj:`Neutrino.update_neutrino`

        Returns:
            bool: ``True`` if updates are available.
        """

        print("\n Checking for updates...", end="")
        self.repo.remotes.origin.fetch()
        updates_available = False

        # if head is in detached state, then return with no updates
        if self.repo.head.is_detached:
            print(" repo's HEAD is detached.")
            return updates_available

        # check for newer commits
        if (
            sum(
                1
                for i in self.repo.iter_commits(
                    f"{self.repo.active_branch.name}..origin/{self.repo.active_branch.name}"
                )
            )
            > 0
        ):
            updates_available = True

        if updates_available:
            update = input(
                " updates are available. \
                \n\n Press [enter] to update the neutrino. Input any other key to continue without updating: "
            )
            if update == "":
                self.update_neutrino(check_completed=True)
                sys.exit()
        else:
            print(" the neutrino is up to date.")

        return updates_available

    def update_neutrino(self, check_completed=False, force=False):
        """Performs the following actions to update the neutrino program:

            1. Checks for updates. If no updates are available, the function is exited.
            2. Performs a ``git pull`` if updates are available.
            3. Checks ``\\setup\\neutrino-settings.yaml`` to see if a ``pip install`` is required.
            4. If required, prompts the user to approve the ``pip install`` action.
            5. If approved, performs the ``pip install`` action.
            6. Displays the change summary from ``\\setup\\neutrino-settings.yaml``.
            7. Exits the program, which must be restarted for the changes to take effect.

        Args:
            check_completed (bool, optional): [description]. Defaults to False.
            force (bool, optional): [description]. Defaults to False.
        """

        if not check_completed and not force:
            self.check_for_updates()
            return

        try:
            # git pull
            self.repo.remotes.origin.pull()

            # git submodule update --init
            for submodule in self.repo.submodules:
                submodule.update(init=True)

            # refresh internal settings
            self.neutrino_settings = t.parse_yaml(
                self.neutrino_dir / "strings/neutrino-settings.yaml", echo_yaml=False
            )

            print(f"\n Updates pulled - change summary:")
            for i in self.neutrino_settings.get("changelog"):
                print(f"   + {i}")

            t.retrieve_repo(verbose=True)

            # if a pip install is required for this update, then do a pip install
            # remember to switch to the neutrino directory first, then switch back after
            # NOTE: permissions issues arise during setup if the user is in a venv
            #       if the user is in a venv, then prompt them to execute the pip install command manually
            if self.neutrino_settings.get("pip_install"):
                print(DIVIDER)
                print("\n A pip install is required to complete this update.")
                if os.environ.get("VIRTUAL_ENV") is not None:
                    input(
                        f" Since you are in a venv, the following command must be executed manually: \
                        \n\n   pip install -U -e . \
                        \n\n Press [enter] or input any key to acknowledge: "
                    )
                else:
                    pip_install = input(
                        f"\n Press [enter] to perform this installation. Input any other key to decline: "
                    )
                    if pip_install == "":
                        print()
                        this_dir = os.getcwd()
                        os.chdir(self.neutrino_dir)
                        subprocess.call("pip install -U -e . --user")
                        os.chdir(this_dir)
                    else:
                        print(
                            f"\n WARNING: pip install not performed - some dependencies may be missing."
                        )

        except Exception as exc:
            print(f"\n Error during self-update process:\n")
            [print(f"   {i}") for i in repr(exc).split("\n")]
            sys.exit(
                "\n Self-update cancelled. Please check your repository configuration and/or try a manual update."
            )

        sys.exit("\n Neutrino annihilated.")

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

    ###########################################################################
    # get methods
    ###########################################################################

    def get_accounts(
        self,
        relevant_only=True,
        exclude_empty_accounts=False,
        from_database=False,
        save=False,
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

        accounts = Datum(
            from_database=from_database,
            link_method=self.request_accounts,
            main_key=self.neutrino_settings.get("response_keys").get("accounts"),
            database_path=self.database_path,
            csv_name="accounts",
        )

        # filter to only accounts that have had some activity at any point in time, if applicable
        if relevant_only:

            # use order history to get list of currencies where activity has been seen
            # TODO: change this to self.get_orders(from_database)
            # temporarily set verbosity to false for the orders retrieval, then switch it back
            initial__verbosity = self.verbose
            self.verbose = False
            orders = self.get_orders(from_database=from_database, status=["all"])
            self.verbose = initial__verbosity
            currencies = (
                orders.df["product_id"]
                .apply(lambda x: x.split("-")[0])
                .unique()
                .tolist()
            )
            accounts.df = accounts.df[
                accounts.df["currency"].isin(currencies)
            ].reset_index(drop=True)

        # exclude accounts with <= 0 balance, if applicable
        if exclude_empty_accounts:
            accounts.df = accounts.df[
                accounts.df["balance"].astype(float) > 0
            ].reset_index(drop=True)

        if self.verbose:
            accounts.print_df()

        if save:
            accounts.save_csv()

        # update object attribute
        self.accounts = accounts

        return accounts

    def get_account_ledger(self, account_id, from_database=False, save=False, **kwargs):

        account_ledger = Datum(
            from_database=from_database,
            link_method=self.request_account_ledger,
            main_key=self.neutrino_settings.get("response_keys").get("ledger"),
            database_path=self.database_path,
            csv_name="ledgers",  # TODO this will be used, but need to do some filtering here
            account_id=account_id,
            **kwargs,
        )

        # APPEND ACCOUNT_ID TO DF COLUMN

        if account_ledger.origin == "db":
            # TODO: data was loaded in from db; filter based on kwargs
            pass

        if self.verbose:
            account_ledger.print_df()

        # update object attribute
        if self.ledgers is None:
            self.ledgers = account_ledger
            # TODO: consider changing main key
        else:
            # TODO: combine ledgers
            pass

        # save to CSV, if applicable
        # ledger data across accounts is stored in a single table

        return account_ledger

    def get_transfers(self, from_database=False, save=False):
        """Loads a DataFrame with in-progress and completed transfers of funds in/out of any of the authenticated profiles' accounts.

        Args:
            from_database (bool, optional): Loads from the local CSV database if ``True``. Otherwise, performs an API request for fresh data. Defaults to ``False``.
            save (bool, optional): Exports the returned DataFrame to a CSV file in the directory specified by ``self.database_path`` if ``True``. Defaults to ``False``.

        Returns:
            DataFrame: DataFrame with the following columns:

                * to be completed
                * at a later date
        """

        transfers = Datum(
            from_database=from_database,
            link_method=self.request_transfers,
            main_key=self.neutrino_settings.get("response_keys").get("transfers"),
            database_path=self.database_path,
            csv_name="transfers",
        )

        if self.verbose:
            transfers.print_df()

        # save to CSV, if applicable
        if save:
            transfers.save()

        # update object attribute
        self.transfers = transfers

        return transfers

    def get_orders(self, from_database=False, save=False, **kwargs):
        """Loads a DataFrame with orders associated with the authenticated profile.

        Args:
            from_database (bool, optional): Loads from the local CSV database if ``True``. Otherwise, performs an API request for fresh data. Defaults to ``False``.
            save (bool, optional): Exports the returned DataFrame to a CSV file in the directory specified by ``self.database_path`` if ``True``. Defaults to ``False``.
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
            DataFrame: DataFrame with the following columns:
            
                * to be completed
                * at a later date
        """

        # TODO: implement kwargs for from_database
        orders = Datum(
            from_database=from_database,
            link_method=self.request_orders,
            main_key=self.neutrino_settings.get("response_keys").get("orders"),
            database_path=self.database_path,
            csv_name="orders",
            **kwargs,
        )

        if orders.origin == "db":
            # TODO: data was loaded in from db; filter based on kwargs <-- or not
            pass

        if self.verbose:
            orders.print_df()

        # save to CSV, if applicable
        if save:
            orders.save_csv()

        # update object attribute
        self.orders = orders

        return orders

    def get_fees(self):
        """Gets the fee rates and 30-day trailing volume for the authenticated profile.

        .. admonition:: TODO

            This is currently just a call to Link's ``retrieve_fees`` function. \
            It should be updated to pull fees from the database using historical data \
            and optionally append fee rates to that data.

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

        self.fees = self.request_fees()

        if self.verbose:
            t.print_recursive_dict(self.fees)

        return self.fees

    def get_all_link_data(self, from_database=False, save=False):
        """Executes all ``retrieve`` methods of the :py:obj:`Neutrino<neutrino.main.Neutrino>`'s inherited :py:obj:`Link<neutrino.link.Link>`:

        * :py:obj:`Link.retrieve_accounts<neutrino.link.Link.retrieve_accounts>`
        * :py:obj:`Link.retrieve_account_ledger<neutrino.link.Link.retrieve_account_ledger>` for all accounts
        * :py:obj:`Link.retrieve_transfers<neutrino.link.Link.retrieve_transfers>`
        * :py:obj:`Link.retrieve_orders<neutrino.link.Link.retrieve_orders>`
        * :py:obj:`Link.retrieve_fees<neutrino.link.Link.retrieve_fees>`

        Args:
            save (bool, optional): Exports DataFrames returned from the above ``retrieve`` methods to the ``self.database`` directory \
                in CSV format if set to ``True``. Defaults to False.
        """

        # get all active accounts - use default options for now
        # TODO: generalize for all options
        account_df = t.process_df(
            self.get_accounts(from_database=from_database, save=save)
        )

        # export ledgers for all those accounts
        ledgers = {}
        for i in account_df.index:
            ledgers[i] = self.get_account_ledger(account_df.at[i, "id"])

        # get all transfers
        self.get_transfers(from_database=from_database, save=save)

        # get all orders
        self.get_orders(from_database=from_database, save=save, status=["all"])

        # get fees
        self.get_fees()

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
            self.neutrino_settings.get("stream_url"),
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

    def interact(self):
        """Temporary rudimentary command line interface that executes neutrino-related commands from user input. \
        The jankiness of this implementation and availability of modules such as ``argparse`` are well-understood. \
        This is mostly used for highly flexible testing/debugging during development.

        This function is wrapped in a ``while True`` block to execute an arbitrary number of commands \
        until terminated by the user.

        Further documentation TBD.
        """

        # set verbosity to True to print outputs to console
        self.set_verbosity(True)

        # continuously accept user input
        while True:

            try:

                print(DIVIDER)

                # gather user input as a list of tokens
                arg = input("\n>>> ").split()

                # reload user settings (user can update settings file prior to providing new command)
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
                    print("\n Help coming soon.")

                # print self attributes/internal data
                if arg[0] in ("state"):
                    print("\n State coming soon.")

                # update cbkey_set used for authentication
                elif arg[0] == "cbkeys":

                    # TODO: display default value and prompt user to accept or override this default w/ list of acceptable values
                    if len(arg) == 1:
                        print(
                            f"\n No keys provided. Please provide a value for cbkey_set_name."
                        )

                    else:
                        self.update_auth(arg[1])
                        print(f"\n self authentication keys changed to: {arg[1]}")

                # parse 'get' statements
                elif arg[0] == "get":

                    # establish whether or not to export retrieved data to CSV
                    save = True if arg[-1] == "-s" else False
                    from_database = True if arg[-1] == "-d" else False

                    # TODO: prompt user w/ list of acceptable values
                    if len(arg) == 1:
                        print(
                            f"\n No 'get' method provided. Please specify what should be retrieved."
                        )

                    elif arg[1] == "accounts":
                        self.get_accounts(save=save, from_database=from_database)

                    elif arg[1] == "ledger":

                        if len(arg) > 2:
                            currency = arg[2]
                        else:
                            print("\n No currency provided - using BTC as default:")
                            currency = "BTC"

                        self.get_account_ledger(
                            self.accounts.get("id", currency),
                            save=save,
                            from_database=from_database,
                        )

                    elif arg[1] == "transfers":
                        self.get_transfers(save=save, from_database=from_database)

                    elif arg[1] == "orders":

                        if len(arg) > 2:
                            if not save and not from_database:
                                self.get_orders(save=save, status=arg[2:])
                            else:
                                self.get_orders(
                                    save=save,
                                    from_database=from_database,
                                    status=arg[2:-1],
                                )
                        else:
                            self.get_orders()

                    elif arg[1] == "fees":
                        self.get_fees()

                    elif arg[1] == "candles":
                        self.get_product_candles(
                            self.user_settings.get("candles").get("product_id"),
                            granularity=self.user_settings.get("candles").get(
                                "granularity"
                            ),
                            start=self.user_settings.get("candles").get("start"),
                            end=self.user_settings.get("candles").get("end"),
                            save=save,
                        )

                    elif arg[1] == "all":
                        self.get_all_link_data(save=save)

                    else:
                        print(f"\n Unrecognized 'get' method: {arg[1]}")

                # set Link verbosity
                elif arg[0] == "verbosity":

                    # hard-code for now - this is a temporary proof-of-concept
                    if len(arg) == 1:
                        print(
                            f"\n No verbosity option specified. Acceptable arguments are 'on' or 'off'."
                        )

                    elif arg[1] == "on":
                        self.set_verbosity(True)

                    elif arg[1] == "off":
                        self.set_verbosity(False)

                    else:
                        print(f"\n Unrecognized verbosity specification: {arg[1]}")

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
                        self.update_self(check_completed=True)
                    else:
                        self.update_self()

                else:
                    print("\n Unrecognized command.")

            except Exception as exc:
                if exc == "\n self annihilated.":
                    break
                else:
                    print(
                        "\n ERROR: prototype interface has encountered the following exception:\n"
                    )
                    traceback.print_exc()


if __name__ == "__main__":

    main()
