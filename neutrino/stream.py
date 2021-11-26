import json
import neutrino.tools as t
import time
import traceback
from threading import Thread
from websocket import create_connection


class Stream:
    def __init__(self, name, url, type, product_ids, channels, auth_keys=None):

        # create requestn for the stream
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
        """open a websocket connection and stream data from coinbase until stream is killed"""

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
                # get websocket message and load into dictionary
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
        """sets self.kill_order to True, which kills the stream upon receipt of the next message"""

        # TODO: kill the stream immediately, instead of depending on next message

        self.kill_order = True

    def close(self):
        """performs actions to close the stream"""

        self.socket.close()
        self.active = False
        print(f"\n stream '{self.name}' closed")
