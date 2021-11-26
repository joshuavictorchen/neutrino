import yaml
import sys
import time
from dateutil.parser import isoparse
from datetime import datetime, timezone
import hmac
import base64
import hashlib
from requests.auth import AuthBase
import git
import os

TIME_FORMAT = "%Y-%m-%d %H:%M"


class Authenticator(AuthBase):
    """custom callable authentication class for coinbase websocket and API authentication
    https://docs.python-requests.org/en/latest/user/advanced/#custom-authentication"""

    def __init__(self, cbkey_set):

        self.cbkey_set = cbkey_set

    def __call__(self, request):
        """modify and return a request with authentication headers"""

        timestamp = str(time.time())
        message = "".join(
            [timestamp, request.method, request.path_url, (request.body or "")]
        )
        request.headers.update(
            generate_auth_headers(timestamp, message, self.cbkey_set)
        )

        return request


def generate_auth_headers(timestamp, message, cbkey_set):
    """generate headers for coinbase websocket and API authentication
    https://docs.cloud.coinbase.com/exchange/docs/authorization-and-authentication"""

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


def print_git():
    """print metadata on local neutrino repo"""

    repo = git.Repo(
        f"{os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))}",
        search_parent_directories=True,
    )

    branch_name = repo.active_branch.name
    commit_id = repo.head.object.hexsha[:7]
    is_dirty = repo.is_dirty(untracked_files=True)

    output = f"\n n | {branch_name}-{commit_id}"
    if is_dirty:
        output += "-modified"

    print(output)


def parse_yaml(filepath, echo_yaml=True, indent_spaces=3, indent_step=2):
    """parse a yaml file, return a dict, and optionally echo formatted data to the console"""

    with open(filepath) as stream:
        try:
            yaml_data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            sys.exit(exc)

    if echo_yaml:
        print_recursive_dict(yaml_data, indent_spaces, indent_step)

    return yaml_data


def print_recursive_dict(data, indent_spaces=3, indent_step=2, recursion=False):
    """print a formatted nested dictionary to the console"""

    if not recursion:
        print()
    for key, value in data.items():
        rjust = len(max(data, key=len))
        if isinstance(value, dict):
            print(" " * indent_spaces + f"{key.rjust(rjust)} : ")
            print_recursive_dict(
                vert_list(value, rjust),
                indent_spaces + indent_step + rjust + 1,
                indent_step,
                True,
            )
        else:
            print(
                " " * indent_spaces
                + f"{key.rjust(rjust)} : {vert_list(value, rjust + indent_spaces + 3)}"
            )

    return True


def vert_list(value, rjust=1):
    """return a formatted string that displays a list as a column"""

    # TODO: update to make recursive for [{}, {}] values

    if not isinstance(value, list):
        return value
    elif len(value) == 0:
        return ""
    elif len(value) == 1:
        return value[0]
    else:
        return_string = str(value[0]) + "\n"
        for i in range(1, len(value)):
            return_string += (" " * rjust) + str(value[i]) + "\n"
        return return_string.strip()


def iso_to_local(iso_string):
    """convert an ISO 8601 string to a datetime object (local timezone)"""

    return isoparse(iso_string).replace(tzinfo=timezone.utc).astimezone(tz=None)


def local_to_iso(time_string, time_format):
    """convert a formatted time string to ISO 8601"""

    datetime.utcfromtimestamp(
        int(time.mktime(time.strptime(time_string, time_format)))
    ).isoformat


def dt_to_string(dt, time_format=TIME_FORMAT):
    """convert a datetime object to a formatted string"""

    return datetime.strftime(dt, time_format)


def string_to_dt(time_string, time_format=TIME_FORMAT):

    return datetime.strptime(time_string, time_format)


def iso_to_local_string(iso_string, time_format=TIME_FORMAT):
    """convert an ISO 8601 string to a formatted local time string"""

    return dt_to_string(iso_to_local(iso_string), time_format)
