import os
import neutrino.interface as interface
import neutrino.tools as t
import subprocess
import sys
from neutrino.link import Link
from neutrino.stream import Stream
from pathlib import Path
from threading import Thread


def main():

    # print repository data
    t.retrieve_repo(verbose=True)

    # instantiate a Neutrino
    # hard-code 'default' cbkey_set_name for now
    # TODO: make this an input parameter and/or echo list of default values
    n = Neutrino("default")

    # perform actions
    interface.interact(n)

    # exit program
    print("\n Neutrino annihilated.")
    print(interface.DIVIDER)


class Neutrino:
    """Handles :py:obj:`Streams<neutrino.stream.Stream>` (WebSocket feed messages) and :py:obj:`Links<neutrino.link.Link>` (API requests/responses). \
        Framework for performing Coinbase Pro actions.

    .. note::

        Authentication is currently handled using a plaintext YAML file defined in ``user-settings.yaml``. \
        It will be updated to use a more secure method in the future.

    Args:
        cbkey_set_name (str, optional): Name of Coinbase Pro API key dictionary \
            with which the Neutrino's ``auth`` value will be initialized. Defaults to "default".

    **Instance attributes:** \n
        * **placeholder** (*placeholder*): Placeholder text.
        * **coins** (*dict*): To be implemented - dict for each coin containing account info, orders, transfers.
    """

    def __init__(self, cbkey_set_name="default"):

        # establish directory in which neutrino is installed
        self.neutrino_dir = Path(
            os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
        )

        # establish locations of files and folders
        self.user_settings_file = self.neutrino_dir / "user-settings.yaml"
        self.template_user_settings_file = (
            self.neutrino_dir / "strings/template-user-settings.yaml"
        )
        self.database_path = self.neutrino_dir / "database"

        # load settings
        self.user_settings = t.load_yaml_settings(
            self.user_settings_file, self.template_user_settings_file
        )
        self.neutrino_settings = t.parse_yaml(
            self.neutrino_dir / "strings/neutrino-settings.yaml", echo_yaml=False
        )
        self.repo = t.retrieve_repo()

        # check for updates
        if self.user_settings.get("check_for_updates"):
            self.check_for_updates()

        # temporary measure for testing: update keys file to sanbox test keys, if keys_file does not exist
        if not os.path.isfile(self.user_settings.get("keys_file")):
            self.user_settings["keys_file"] = (
                self.neutrino_dir / "tests/sandbox-keys.yaml"
            )

        # establish unique neutrino attributes
        self.cbkeys = t.parse_yaml(self.user_settings.get("keys_file"), echo_yaml=False)
        self.update_auth(cbkey_set_name)
        self.link = Link(
            "default_link",
            self.neutrino_settings.get("api_url"),
            self.auth,
            self.database_path,
        )
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

            # if a pip install is required for this update, then do a pip install
            # remember to switch to the neutrino directory first, then switch back after
            if self.neutrino_settings.get("pip_install"):
                pip_install = input(
                    f"\n A pip install is required for this update. \
                    \n\n Press [enter] to perform this installation. Input any other key to decline: "
                )
                if pip_install == "":
                    print()
                    this_dir = os.getcwd()
                    os.chdir(self.neutrino_dir)
                    subprocess.call("pip install -U -e . --user", shell=True)
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

        print(f"\n Update complete - change summary:")
        for i in self.neutrino_settings.get("changelog"):
            print(f"   + {i}")

        t.retrieve_repo(verbose=True)

        sys.exit("\n Neutrino annihilated.")

    def refresh_user_settings(self):
        """Reloads ``self.user_settings`` from ``self.user_settings_file``. This allows the user to update the \
            user settings file with different inputs between Neutrino commands.
        """

        self.user_settings = t.load_yaml_settings(
            self.user_settings_file, self.template_user_settings_file
        )

    def update_auth(self, cbkey_set):
        """Updates the keys used for authenticating Coinbase WebSocket and API requests.

        Args:
            cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`neutrino.tools.Authenticator`.
        """

        self.auth = t.Authenticator(self.cbkeys.get(cbkey_set))

        if hasattr(self, "link"):
            self.link.update_auth(self.auth)

    def get_all_link_data(self, save=False):
        """Executes all ``get`` methods of the :py:obj:`Neutrino<neutrino.main.Neutrino>`'s :py:obj:`Link<neutrino.link.Link>`:

        * :py:obj:`Link.get_accounts<neutrino.link.Link.get_accounts>`
        * :py:obj:`Link.get_account_ledger<neutrino.link.Link.get_account_ledger>` for all accounts
        * :py:obj:`Link.get_transfers<neutrino.link.Link.get_transfers>`
        * :py:obj:`Link.get_orders<neutrino.link.Link.get_orders>`
        * :py:obj:`Link.get_fees<neutrino.link.Link.get_fees>`

        Args:
            save (bool, optional): Exports data returned from the above ``get`` methods to the ``database`` directory \
                in CSV format if set to ``True``. Defaults to False.
        """

        # get all active accounts
        account_df = self.link.get_accounts(save=save)

        # export ledgers for all those accounts
        ledgers = {}
        for i in account_df.index:
            ledgers[i] = self.link.get_account_ledger(account_df.at[i, "id"], save=save)

        # get all transfers
        self.link.get_transfers(save=save)

        # get all orders
        self.link.get_orders(save=save, status=["all"])

        # get fees
        self.link.get_fees()

    def load_product_candles(self, product_id, granularity=60, start=None, end=None):

        # if dbfile exists, then generate pull bounds

        # 

        pass

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


if __name__ == "__main__":

    main()
