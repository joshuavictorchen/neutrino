import neutrino.config as c
import os
import shutil
import sys
import yaml
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse


def print_recursive_dict(data, indent_spaces=3, indent_step=2, recursion=False):
    """Prints a formatted nested dictionary to the console.

    .. code-block::

        # example console output for an input of {'123':{'456':['aaa', 'bbb', 'ccc']}}

        "
            123 :
                    456 : aaa
                        bbb
                        ccc"

    Args:
        data (dict): Dictionary of values that can be converted to strings.
        indent_spaces (int, optional): Number of leading whitespaces to insert before each element. Defaults to 3.
        indent_step (int, optional): Number of whitespaces to increase the indentation by, for each level of ``dict`` nesting. Defaults to 2.
        recursion (bool, optional): Whether or not this method is being called by itself. Defaults to False.

    """

    # print a newline once, prior to the formatted dictionary
    if not recursion:
        print()

    # loop through the dictionary
    for key, value in data.items():

        # the right-justification for each key is equal to the length of the longest key
        rjust = len(max(data, key=len))

        # if the value is a dictionary, then recursively call this function to print the inner dictionary
        if isinstance(value, dict):
            print(" " * indent_spaces + f"{key.rjust(rjust)} : ")
            print_recursive_dict(
                list_to_string(value, rjust),
                indent_spaces
                + indent_step
                + rjust
                + 1,  # adjust the indentation level of the inner dictionary
                indent_step,
                True,
            )

        # if the value is not a dictionary, then print the key-value pair
        else:
            print(
                " " * indent_spaces
                + f"{key.rjust(rjust)} : {list_to_string(value, rjust + indent_spaces + 3)}"
            )


def list_to_string(value, leading_whitespaces=1):
    """Takes a list and returns a formatted string containing each element delimited by newlines.

    .. admonition:: TODO

        Incorporate :py:obj:`print_recursive_dict` for lists with dictionary elements, i.e. ``[{}, {}]``.

    Args:
        value (list): A list of elements that can be represented by strings.
        leading_whitespaces (int, optional): Number of leading whitespaces to insert before each element. Defaults to 1.

    Returns:
        str: Formatted string containing each element of the provided list delimited by newlines, with ``leading_whitespaces`` leading whitespaces before each element.

        .. code-block::

            # example returned string for an input of ['abc', 'def', 'ghi']

            " abc\\n def\\n ghi"
    """

    # just return the same value if it's not a list
    if not isinstance(value, list):
        return value
    # if the list is empty, then return a blank string
    elif len(value) == 0:
        return ""
    # if the list has only one element, then return that element
    elif len(value) == 1:
        return value[0]
    # if the list has more than one element, then return a string containing each element delimited by newlines
    # add leading_whitespaces number of leading whitespaces before each element
    else:
        return_string = str(value[0]) + "\n"
        for i in range(1, len(value)):
            return_string += (" " * leading_whitespaces) + str(value[i]) + "\n"
        return return_string.strip()


def load_yaml_settings(settings_file, settings_template_file):
    """Loads a dictionary of settings values from a YAML file.

    This YAML file is gitignored so that the repository's configuration is not affected by user personalization.

    If the YAML file does not exist, then it is copied from the repository's version controlled template.

    Args:
        settings_file (str): Absolute path to the gitignored YAML file.
        settings_template_file (str): Absolute path to the version controlled YAML template.

    Returns:
        dict: Dictionary representation of loaded settings from a YAML file.
    """

    # if file does not exist, copy one from the default template
    if not os.path.isfile(settings_file):
        # TODO: prompt user to update keys_file defs, etc.
        shutil.copy2(settings_template_file, settings_file)
        print(f"\n Settings file generated: {settings_file}")

    settings = parse_yaml(settings_file, echo_yaml=False)

    return settings


def parse_yaml(filepath, echo_yaml=True):
    """Parses a YAML file and returns a dict of its contents. Optionally prints the formatted dict to the console.

    Args:
        filepath (str): Path to the supplied YAML file.
        echo_yaml (bool, optional): Whether or not to print the formatted loaded dict to the console. Defaults to True.

    Returns:
        dict: Dictionary of contents loaded from the supplied YAML file.
    """

    # open the file and load its data into a dict
    with open(filepath) as stream:
        try:
            yaml_data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            sys.exit(f"\n Neutrino annihilated - YAML file is corrupted:\n\n {exc}")

    # if echo_yaml is True, then print the formatted dict to the console
    if echo_yaml:
        print_recursive_dict(yaml_data)

    return yaml_data


def save_df_to_csv(df, csv_name, database_path):
    """Exports the provided DataFrame to a CSV file. Cleans timestrings per :py:obj:`clean_df_timestrings`.\
        Prompts the user to close the file if it exists and is open.

    Args:
        df (DataFrame): DataFrame to be exported to a CSV file.
        csv_name (str): Name of the CSV file to be saved, **without** the ``.csv`` extension \
            (i.e., ``saved_file`` instead of ``saved_file.csv``).
        database_path (Path): Absolute path to the directory in which the CSV file will be saved.
    """

    # TODO: default behavior should be to APPEND to CSV, with option to OVERWRITE

    filepath = database_path / (csv_name + ".csv")
    df = clean_df_timestrings(df)

    while True:
        try:
            df.to_csv(filepath, index=False)
            break
        except PermissionError:
            response = input(
                f"\n Error exporting {csv_name} to CSV: {filepath} is currently open.\
                \n Close the file and press [enter] to continue. Input any other key to abort: "
            )
            if response != "":
                print(f"\n {csv_name} CSV not saved.")
                return

    print(f" \n {csv_name} exported to: {filepath}")


def clean_df_timestrings(df):
    """Ensure the provided DataFrame's time string columns are properly formatted (``%Y-%m-%d %H:%M``). \
    This is needed because timestrings loaded into a DataFrame from a CSV file may be automatically reformatted \
    into another configuration.

    .. note::
    
        This does not affect time strings stored in ISO 8601 format.

    Args:
        df (DataFrame): DataFrame to be processed.

    Returns:
        DataFrame: DataFrame object with cleaned time string columns.
    """

    # use the add_minutes_to_time_string method (adding 0 minutes) on each column
    # this ensures proper time string formatting for all columns containing generic time string strings
    for column in df:
        try:
            df[column] = df[column].apply(lambda x: add_minutes_to_time_string(x, 0))
        except:
            pass

    return df


def move_df_column_inplace(df, column, position):
    """Moves a DataFrame column to the specified index position inplace.

    Credit: https://stackoverflow.com/a/58686641/17591579

    Args:
        df (DataFrame): DataFrame whose columns will be rearranged.
        column (str): Name of the column to be moved.
        position (int): Index to which the column will be moved.
    """

    column = df.pop(column)
    df.insert(position, column.name, column)


def local_to_ISO_time_string(local_time_string, time_format=c.TIME_FORMAT):
    """Converts a local time string to an ISO 8601 time string.

    Example use case: converting user-specified start/end times in Link.get_product_candles().

    Args:
        local_time_string (string): Time string with the specified time_format.
        time_format (string, optional): Format of local_time_string.

    Returns:
        str: ISO 8601 time string.
    """

    # use epoch as an intermediary for conversion
    return datetime.utcfromtimestamp(
        datetime.timestamp(datetime.strptime(local_time_string, time_format))
    ).isoformat()


def ISO_to_local_time_dt(ISO_time_string):
    """Converts an ISO 8601 time string to a local-timezone datetime object.

    Example use case: converting API-retrieved timestamps to a usable format for data processing.

    Args:
        ISO_time_string (str): ISO 8601 time string.

    Returns:
        datetime: Datetime object (local timezone).
    """

    return isoparse(ISO_time_string).replace(tzinfo=timezone.utc).astimezone(tz=None)


def ISO_to_local_time_string(ISO_time_string, time_format=c.TIME_FORMAT):
    """Converts an ISO 8601 time string to a local time string.

    Example use case: converting API-retrieved timestamps to local time format for output to the console.

    Args:
        ISO_time_string (str): ISO 8601 time string.
        time_format (str, optional): Format of the returned local time string.

    Returns:
        str: Local time string.
    """

    return datetime.strftime(ISO_to_local_time_dt(ISO_time_string), time_format)


def add_minutes_to_time_string(time_string, minute_delta, time_format=c.TIME_FORMAT):
    """Adds minutes to a given time string and returns the result as another time string.

    Args:
        time_string (str): Original time string.
        minute_delta (int): Minutes to add to the original time string. Can be negative.
        time_format (str, optional): Format of the provided and returned time strings.

    Returns:
        str: Result from time_string plus minute_delta.
    """

    return datetime.strftime(
        datetime.strptime(time_string, time_format) + timedelta(minutes=minute_delta),
        time_format,
    )
