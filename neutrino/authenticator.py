import base64
import hashlib
import hmac
import time
from requests.auth import AuthBase


class Authenticator(AuthBase):
    """Custom callable authentication class for Coinbase WebSocket and API authentication:

    https://docs.python-requests.org/en/latest/user/advanced/#custom-authentication

    **Instance attributes:** \n
    * **cbkey_set** (*dict*): Dictionary of API keys with the following format:

        .. code-block::

            {
                    public: <public-key-string>
                   private: <secret-key-string>
                passphrase: <passphrase-string>
            }

    """

    def __init__(self, cbkey_set):

        self.cbkey_set = cbkey_set

    def __call__(self, request):
        """Adds authentication headers to a request and returns the modified request."""

        timestamp = str(time.time())
        message = "".join(
            [timestamp, request.method, request.path_url, (request.body or "")]
        )
        request.headers.update(
            self.generate_auth_headers(timestamp, message, self.cbkey_set)
        )

        return request

    @staticmethod
    def generate_auth_headers(timestamp, message, cbkey_set):
        """Generates headers for authenticated Coinbase WebSocket and API messages:

        https://docs.cloud.coinbase.com/exchange/docs/authorization-and-authentication

        Args:
            timestamp (str): String representing the current time in seconds since the Epoch.
            message (str): Formatted message to be authenticated.
            cbkey_set (dict): Dictionary of API keys with the format defined in :py:obj:`Authenticator`.

        Returns:
            dict: Dictionary of authentication headers with the following format:

            .. code-block::

                {
                            Content-Type: 'Application/JSON'
                          CB-ACCESS-SIGN: <base64-encoded-message-signature>
                     CB-ACCESS-TIMESTAMP: <message-timestamp>
                           CB-ACCESS-KEY: <public-key-string>
                    CB-ACCESS-PASSPHRASE: <passphrase-string>
                }
        """

        message = message.encode("ascii")
        hmac_key = base64.b64decode(cbkey_set.get("private"))
        signature = hmac.new(hmac_key, message, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode("utf-8")
        return {
            "Content-Type": "Application/JSON",
            "CB-ACCESS-SIGN": signature_b64,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-KEY": cbkey_set.get("public"),
            "CB-ACCESS-PASSPHRASE": cbkey_set.get("passphrase"),
        }
