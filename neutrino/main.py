import os
from neutrino.link import Link
import time
import sys
import neutrino.tools as t
from neutrino.stream import Stream
from threading import Thread


NEUTRINODIR = (
    f"{os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))}"
)
SETTINGSFILE = f"{NEUTRINODIR}\\settings.yaml"


def main():

    t.print_git()
    n = Neutrino('default')

    try:
        l = Link('testlink', n.settings.get('api_url'), n.auth)
        t.print_recursive_dict(l.get_user_accounts())
        t.print_recursive_dict(l.get_orders())
        t.print_recursive_dict(
            l.get_account_ledger(n.test_parameters.get("test_account_id"))
        )
        n.configure_new_stream("teststream", ["BTC-USD"], ["ticker"])
        n.start_stream("teststream")
        n.parse_stream_messages("teststream")
        n.streams.get("teststream").kill()
    except KeyboardInterrupt as e:
        for stream in n.streams:
            n.streams.get(stream).kill()
            n.threads.get(stream).join()
        try:
            sys.exit(e)
        except Exception as e:
            os._exit(e)

    print("\n fin")


class Neutrino:
    """Handles Streams (WebSocket feed messages) and Links (API requests/responses). Framework for performing Coinbase Pro actions.

    Args:
        cbkey_set (str, optional): Name of Coinbase Pro API key dictionary. If provided, the Neutrino's ``auth`` value will be initialized.
    
    Instance attributes
        * this is a test \n
          this is a continuation
        * another bullet
    """

    def __init__(self, cbkey_set=None):

        self.settings = t.parse_yaml(SETTINGSFILE, echo_yaml=False)
        self.cbkeys = t.parse_yaml(self.settings.get("keys_file"), echo_yaml=False)
        self.test_parameters = t.parse_yaml(
            self.settings.get("test_parameters_file"), echo_yaml=False
        )
        self.streams = {}
        self.threads = {}
        self.links = {}
        self.accounts = None
        self.coins = {}
        if self.cbkeys:
            self.update_auth_keys(cbkey_set)

    def update_auth_keys(self, cbkey_set):
        """update the keys used for authenticated coinbase websocket and API requests"""

        self.auth = t.Authenticator(self.cbkeys.get(cbkey_set))

    def configure_new_stream(
        self, name, product_ids, channels, type="subscribe", cbkey_set="default"
    ):
        """set up a new coinbase websocket stream

        Args:
            name (string): stream name
            product_ids (list): list of strings
            channels (list): list of channels
            type (str, optional): message type
            cbkey_set (str, optional): api keys to use

        Raises:
            ValueError: if the stream already exists
        """

        # raise exception if stream already exists
        if name in self.streams:
            raise ValueError(f"\n stream '{name}' already exists")

        # TODO: error handling and reqs checking for arguments

        # get keys for authentication - default is the 'default' key name; if no key is provided, then None is passed (no auth)
        auth_keys = self.cbkeys.get(cbkey_set)

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
        """start a configured coinbase websocket stream thread"""

        self.threads.get(stream_name).start()

    def parse_stream_messages(self, stream_name):
        """test function to parse stream messages

        Args:
            stream_name (string): name of stream whom's messages to parse
        """

        parsed_message_count = 0
        while True:
            # get streamed data, which is a tuple of the form: (message count, message)
            stream_data = self.streams.get(stream_name).latest_message
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
        """temporary test actions taken upon receipt of a ticker websocket message"""

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
            + t.iso_to_local_string(message.get("time"), "%Y-%m-%d %H:%M:%S")
            + f' | {ticker_product} {pdelta} | {message.get("price")}'
        )


if __name__ == "__main__":

    main()
