import json
import time
import traceback
from neutrino.authenticator import Authenticator
from websocket import create_connection


class Stream:
    """Opens a WebSocket connection and streams/stores Coinbase Pro data.

    Further reading: https://docs.cloud.coinbase.com/exchange/docs/overview

    **Instance attributes:** \n
        * **name** (*str*): Stream's name.
        * **url** (*str*): URL endpoint for the Coinbase Pro WebSocket feed.
        * **request** (*str*): Request sent to the WebSocket endpoint upon connection. \
            Configured during Stream instantiation.
        * **socket** (*WebSocket*): Stream's WebSocket object.
        * **active** (*bool*): ``True`` if the Stream has a live (connected) WebSocket object, ``False`` otherwise.
        * **kill_order** (*bool*): ``True`` if the WebSocket connection should be closed on the next iteration, \
            ``False`` otherwise.
        * **stored_messages** (*list(dict)*): *to be created*
        * **latest_message** (*tuple(int, dict)*): Tuple containing the total number of WebSocket messages received, \
            along with the latest WebSocket message received.
        * **killed** (*bool*): ``True`` if the Stream has already been started and killed. Dead Streams cannot be revived.

    Args:
        name (str): Unique name for this Stream object.
        url (str): URL endpoint for the Coinbase Pro WebSocket feed.
        type (str): Type of message that is sent to the WebSocket endpoint upon opening a connection \
            (usually 'subscribe').
        product_ids (list(str)): List of coin trading pairs (i.e., ['BTC-USD']).
        channels (list(str)): List of channels specified for the WebSocket connection (i.e., ['ticker']).
        auth_keys (dict(str)): Dictionary of Coinbase Pro API keys with which the Stream's WebSocket connection \
            will be authenticated.
    """

    def __init__(self, name, url, type, product_ids, channels, auth_keys):

        # create request for the stream
        request = {"type": type, "product_ids": product_ids, "channels": channels}

        # authenticate by updating the request with auth fields
        timestamp = str(time.time())
        auth_headers = Authenticator.generate_auth_headers(
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
        self.killed = False

    def stream(self):
        """Opens a WebSocket connection and streams data from the Coinbase Exchange websocket feed \
            until the Stream is killed.

        .. admonition:: TODO

            * Check for (and handle) message errors.
            * Add stored data and periodically flush it (i.e., for live minute-avg calcs, etc.).
        """

        print(f"\n starting stream {self.name}")

        # open socket and update streams dict
        self.socket = create_connection(self.url)
        self.socket.send(json.dumps(self.request))
        self.active = True

        # keep streaming data until self.kill_order = True
        streamed_message_count = 0
        while not self.kill_order:
            try:
                # load WebSocket message into dictionary and store it in self.latest_message
                # along with the message count
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
        """Sets the Stream's :py:obj:`kill_order` attribute to :py:obj:`True`, \
        which kills the Stream upon receipt of the next WebSocket message.

        .. admonition:: TODO

            * Kill the stream immediately instead of depending on the receipt of a new message.
        """

        self.kill_order = True

    def close(self):
        """Closes the Stream's WebSocket connection and sets its ``active`` attribute to ``False`` \
            and ``killed`` attribute to ``True``."""

        self.socket.close()
        self.active = False
        self.killed = True
        print(f"\n stream '{self.name}' closed")
