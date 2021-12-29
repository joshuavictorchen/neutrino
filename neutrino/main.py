import os
import neutrino.interface as i
import neutrino.tools as t
from neutrino.link import Link
from neutrino.stream import Stream
from threading import Thread


NEUTRINODIR = (
    f"{os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))}"
)
SETTINGSFILE = f"{NEUTRINODIR}\\settings.yaml"


def main():

    # print repository data
    t.print_git()

    # instantiate a Neutrino
    # hard-code 'default' cbkey_set_name for now
    # TODO: make this an input parameter and/or echo list of default values
    n = Neutrino("default")

    # perform actions
    i.interact(n)

    # exit program
    print("\n Neutrino annihilated.")
    print(i.DIVIDER)


class Neutrino:
    """Handles :py:obj:`Streams<neutrino.stream.Stream>` (WebSocket feed messages) and :py:obj:`Links<neutrino.link.Link>` (API requests/responses). \
        Framework for performing Coinbase Pro actions.

    .. note::

        Authentication is currently handled using a plaintext YAML file defined in ``settings.yaml``. \
        It will be updated to use a more secure method in the future.

    Args:
        cbkey_set_name (str, optional): Name of Coinbase Pro API key dictionary \
            with which the Neutrino's ``auth`` value will be initialized. Defaults to "default".

    **Instance attributes:** \n
        * **placeholder** (*placeholder*): Placeholder text.
        * **coins** (*dict*): To be implemented - dict for each coin containing account info, orders, transfers.
    """

    def __init__(self, cbkey_set_name="default"):

        self.settings = t.parse_yaml(SETTINGSFILE, echo_yaml=False)
        self.cbkeys = t.parse_yaml(self.settings.get("keys_file"), echo_yaml=False)
        self.test_parameters = t.parse_yaml(
            self.settings.get("test_parameters_file"), echo_yaml=False
        )
        self.update_auth(cbkey_set_name)
        self.link = Link("default_link", self.settings.get("api_url"), self.auth)
        self.streams = {}
        self.threads = {}
        self.coins = {}

    def update_auth(self, cbkey_set):
        """Updates the keys used for authenticating Coinbase WebSocket and API requests.

        Args:
            cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`neutrino.tools.Authenticator`.
        """

        self.auth = t.Authenticator(self.cbkeys.get(cbkey_set))

        if hasattr(self, "link"):
            self.link.update_auth(self.auth)

    def get_all_link_data(self, save=False):

        # test method

        # get all active accounts
        account_df = self.link.get_accounts(exclude_empty_accounts=True)

        # export ledgers for all those accounts
        ledgers = {}
        for i in account_df.index:
            ledgers[i] = self.link.get_account_ledger(account_df.at[i, "id"])

        # get all transfers
        transfers_df = self.link.get_usd_transfers()

        # get all orders
        orders_df = self.link.get_orders(status=["all"])

        # get fees
        self.link.get_fees()

        # return without saving CSVs if save = False
        if not save:
            return

        # save CSVs
        account_df.to_csv(
            self.settings.get("csv_directory") + "\\accounts.csv", index=False
        )
        for i in account_df.index:
            ledgers.get(i).to_csv(
                self.settings.get("csv_directory")
                + f"\\{account_df.at[i, 'currency']}.csv",
                index=False,
            )
        transfers_df.to_csv(
            self.settings.get("csv_directory") + "\\transfers.csv", index=False
        )
        orders_df.to_csv(
            self.settings.get("csv_directory") + "\\orders.csv", index=False
        )

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
            self.settings.get("stream_url"),
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
