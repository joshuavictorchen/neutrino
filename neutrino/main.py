import os
import neutrino.tools as t
import sys
from neutrino.link import Link
from neutrino.stream import Stream
from threading import Thread


NEUTRINODIR = (
    f"{os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))}"
)
SETTINGSFILE = f"{NEUTRINODIR}\\settings.yaml"
DIVIDER = (
    "\n -------------------------------------------------------------------------------"
)


def main():

    # print repository data
    t.print_git()

    # instantiate a Neutrino
    # hard-code 'default' cbkey_set_name for now
    # TODO: make this an input parameter and/or echo list of default values
    n = Neutrino("default")

    # continuously accept user input
    while True:

        print(DIVIDER)

        # gather user input as a list of tokens
        arg = input("\n>>> ").split()

        # don't do anything if no input was provided
        if len(arg) == 0:
            continue

        # exit the program if 'quit' or 'q' are entered
        if arg[0] in ("quit", "q"):
            break

        # print list of available commands
        if arg[0] in ("help", "h"):
            print("\n Help coming soon.")

        # update cbkey_set used for authentication
        elif arg[0] == "cbkeys":

            # TODO: display default value and prompt user to accept or override this default w/ list of acceptable values
            if len(arg) == 1:
                print(
                    f"\n No keys provided. Please provide a value for cbkey_set_name."
                )

            else:
                n.update_auth(arg[1])
                print(f"\n Neutrino authentication keys changed to: {arg[1]}")

        # parse 'get' statements
        elif arg[0] == "get":

            # TODO: prompt user w/ list of acceptable values
            if len(arg) == 1:
                print(
                    f"\n No 'get' method provided. Please specify what should be retrieved."
                )

            elif arg[1] == "accounts":
                n.link.get_accounts()

            elif arg[1] == "ledger":
                # TODO: next arg should be an account ID; hardcode with sample ID for now
                n.link.get_account_ledger(n.test_parameters.get("test_account_id"))

            elif arg[1] == "transfers":
                n.link.get_account_transfers()

            elif arg[1] == "orders":
                n.link.get_orders(status=["all"])

            elif arg[1] == "fees":
                n.link.get_fees()

            elif arg[1] == "candles":
                # TODO: next arg should be a coin pair; hardcode with BTC-USD for now
                # l.get_product_candles("BTC-USD")
                n.link.get_product_candles(
                    "BTC-USD", start="2021-01-01 00:00", end="2021-01-02 00:00"
                )

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
                n.link.set_verbosity(True)

            elif arg[1] == "off":
                n.link.set_verbosity(False)

            else:
                print(f"\n Unrecognized verbosity specification: {arg[1]}")

        # stream data
        elif arg[0] == "stream":

            # hard-code for now - in future, split into components, let user append items to lists, etc.
            # NOTE: this means right now, you can't execute this command more than once within the same instance of the program
            try:
                n.configure_new_stream("teststream", ["BTC-USD"], ["ticker", "user"])
                n.start_stream("teststream")
                n.parse_stream_messages("teststream")
                n.streams.get("teststream").kill()
            except KeyboardInterrupt:
                for stream in n.streams:
                    n.streams.get(stream).kill()
                    n.threads.get(stream).join()

        else:
            print("\n Unrecognized command.")

    print("\n Neutrino annihilated.")
    print(DIVIDER)


class Neutrino:
    """Handles Streams (WebSocket feed messages) and Links (API requests/responses). Framework for performing Coinbase Pro actions.

    .. note::

        Authentication is currently handled using a plaintext YAML file defined in ``settings.yaml``. \
        It will be updated to use a more secure method in the future.

    Args:
        cbkey_set_name (str, optional): Name of Coinbase Pro API key dictionary. If provided, the Neutrino's ``auth`` value will be initialized.

    **Instance attributes:** \n
        * **placeholder** (*placeholder*): Placeholder text.
        * **coins** (*dict*): To be implemented - dict for each coin containing account info, orders, transfers.
    """

    def __init__(self, cbkey_set_name=None):

        self.settings = t.parse_yaml(SETTINGSFILE, echo_yaml=False)
        self.cbkeys = t.parse_yaml(self.settings.get("keys_file"), echo_yaml=False)
        self.test_parameters = t.parse_yaml(
            self.settings.get("test_parameters_file"), echo_yaml=False
        )

        if self.cbkeys:
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

    def configure_new_stream(
        self, name, product_ids, channels, type="subscribe", cbkey_set_name="default"
    ):
        """Instantiates and configures a new :py:obj:`neutrino.stream.Stream` object.

        Updates ``self.streams`` and ``self.threads`` with this object and corresponding thread.

        Args:
            name (str): User-specified name of the new :py:obj:`neutrino.stream.Stream` object.
            product_ids (list(str)): List of coin trading pairs (i.e., ['BTC-USD']).
            channels (list(str)): List of channels specified for the WebSocket connection (i.e., ['ticker']).
            type (str): Type of message that is sent to the WebSocket endpoint upon opening a connection. Defaults to "subscribe".
            cbkey_set_name (str, optional): Name of the ``cbkey_set`` dictionary defined in the cbkeys file. Defaults to "default".

        Raises:
            ValueError: If the specified stream name already exists.
        """

        # raise exception if stream already exists
        if name in self.streams:
            raise ValueError(f"\n stream '{name}' already exists")

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

    def start_stream(self, stream_name):
        """Starts the thread for a configured Coinbase WebSocket stream.

        Args:
            stream_name (str): Name of the configured Coinbase WebSocket stream to be started.
        """

        self.threads.get(stream_name).start()

    def parse_stream_messages(self, stream_name):
        """Test function to parse stream messages.

        Args:
            stream_name (string): Name of stream whom's messages to parse.
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
        """Temporary test actions taken upon receipt of a Coinbase WebSocket ticker message from :py:obj:`neutrino.stream.Stream`.

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
