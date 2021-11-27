import json
import neutrino.tools as t
import time
import traceback
from threading import Thread
from websocket import create_connection


class Stream:
    """Opens a websocket connection and streams/stores Coinbase Pro data.

    Authentication is currently handled using a plaintext dictionary in the following format.
    It will be updated to use a more secure method in the future:

    .. code-block::

        {
            public: <public-key-string>,
            private: <secret-key-string>,
            passphrase: <passphrase-string>
        }

    Args:
        name (str): Unique name for this Stream object.
        url (str): URL endpoint for the Coinbase Pro websocket feed.
        type (str): Type of message that is sent to the websocket endpoint upon opening a connection
                    (usually 'subscribe').
        product_ids (list of str): List of coin trading pairs (i.e., ['BTC-USD']).
        channels (list of str): List of channels specified for the websocket connection (i.e., ['ticker']).
        auth_keys (dict of str, optional): Dictionary of Coinbase Pro API keys.
                                           If provided, the Stream's websocket connection will be authenticated.
    """

    def __init__(self, name, url, type, product_ids, channels, auth_keys=None):

        # create request for the stream
        request = {"type": type, "product_ids": product_ids, "channels": channels}

        # if auth_keys are provided, then authenticate by updating the request with auth fields
        if auth_keys:
            timestamp = str(time.time())
            auth_headers = t.generate_auth_headers(
                timestamp, timestamp + "GET/users/self/verify", auth_keys
            )
            request.update(
                {
                    "signature": auth_headers.get("CB-ACCESS-SIGN"),
                    "key": auth_headers.get("CB-ACCESS-KEY"),
                    "passphrase": auth_headers.get("CB-ACCESS-PASSPHRASE"),
                    "timestamp": auth_headers.get("CB-ACCESS-TIMESTAMP"),
                }
            )

        # establish attributes
        self.name = name
        self.url = url
        self.request = request
        self.socket = None
        self.active = False
        self.kill_order = False
        self.stored_messages = []
        self.latest_message = ()

    def stream(self):
        """Opens a websocket connection and streams data from the Coinbase Pro API until the Stream is killed."""

        print(f"\n starting stream {self.name}")

        # open socket and update streams dict
        self.socket = create_connection(self.url)
        self.socket.send(json.dumps(self.request))
        self.active = True

        # keep streaming data until self.kill_order = True
        # TODO: check for (and handle) message errors
        # TODO: add stored data and periodically flush it (i.e., for live minute-avg calcs, etc.)
        streamed_message_count = 0
        while not self.kill_order:
            try:
                # load websocket message into dictionary and store it in self.latest_message along with the message count
                message = json.loads(self.socket.recv())
                streamed_message_count += 1
                self.latest_message = (streamed_message_count, message)
            except Exception as e:
                self.kill()
                print("\n error while parsing message:\n")
                print(traceback.format_exc().strip())

        # close stream
        self.close()

    def kill(self):
        """Sets the Stream's ``kill_order`` attribute to ``True``,
        which kills the Stream upon receipt of the next websocket message.
        """

        # TODO: kill the stream immediately, instead of depending on next message

        self.kill_order = True

    def close(self):
        """Closes the Stream's websocket connection and sets its ``active`` attribute to ``False``."""

        self.socket.close()
        self.active = False
        print(f"\n stream '{self.name}' closed")
