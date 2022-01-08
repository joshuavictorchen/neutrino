import neutrino
import neutrino.tools as t
import os
import pandas as pd
from copy import deepcopy
from pathlib import Path


class Datum:
    """Loads data from the database or an API request per the user's specification.

    Defaults to performing an API request if database data is requested, but no database file exists.

    .. note::

        ``**kwargs`` arguments are not handled for database pulls. The calling method must handle any actions \
            associated with those parameters if ``db`` is returned.

    Args:
        from_database (bool): ``True`` if data is to be loaded from the CSV database.
        link_method (obj): placeholder
        main_key (str): placeholder
        database_path (Path, optional): Absolute path to the Neutrino's database directory.
        csv_name (str, optional): Name of the CSV file to be loaded from, if applicable, **without** the ``.csv`` extension \
            (i.e., ``loaded_file`` instead of ``loaded_file.csv``).
        link_method (Object, optional): Link's API request method to be called, if not loading from a database file.
        clean_timestrings (bool, optional): Runs :py:obj:`clean_df_timestrings` on the provided DataFrame if ``True``. Defaults to ``False``.

    Returns:
        Datum: TO BE CHANGED Tuple in the form of ``(load_method, df)`` where ``load_method`` is "db" or "api" \
            depending on the actual method used to pull the data, and ``df`` is the DataFrame object \
            containing data loaded in from the specified database file or API request.
    """

    def __init__(self, from_database, link_method, csv_name, **kwargs):

        self.csv_name = csv_name
        self.main_key = neutrino.api_response_keys.get(csv_name)

        api_request = True
        filepath = neutrino.db_path / (csv_name + ".csv")

        if from_database:
            if os.path.isfile(filepath):
                self.df = pd.read_csv(filepath)
                self.origin = "db"
                api_request = False
            else:
                print(
                    f"\n WARNING: {filepath} does not exist.\n\n Data will be pulled via API request."
                )

        if api_request:
            self.df = self.convert_API_response_list_to_df(
                link_method(**kwargs), self.main_key
            )
            self.origin = "api"

        self.df = t.clean_df_timestrings(self.df)

    def convert_API_response_list_to_df(self, response_list, main_key):
        """Converts a list of dicts from a Coinbase API response to a DataFrame.

        Args:
            response_list (list(dict)): Response from a Coinbase API request.
            main_key (str): Key containing a unique identifier for a response element.

        Returns:
            DataFrame: DataFrame of values loaded from a Coinbase API response.
        """

        # create a deepcopy in order to prevent carry-over to/from unrelated method calls, since lists are mutable
        response_list = deepcopy(response_list)

        # convert list of dicts into dict of dicts
        data_dict = {}
        [data_dict.update({i.get(main_key): i}) for i in response_list]

        # create a df object to load data into
        converted_df = pd.DataFrame()

        # prep data and load into converted_df for each coin
        for data_value_dict in data_dict.values():

            for key, value in data_value_dict.copy().items():

                # the Coinbase API nests multiple items under a 'details' key for certain responses
                # un-nest these items and delete the 'details' key for these cases
                # finally, put all values into list format so that they can be loaded via pd.DataFrame.from_dict()
                if key == "details":
                    for inner_key, inner_value in value.items():
                        data_value_dict[inner_key] = [inner_value]
                    data_value_dict.pop(key, None)
                else:
                    data_value_dict[key] = [value]

            # add this data to the df object
            converted_df = converted_df.append(
                pd.DataFrame.from_dict(data_value_dict), ignore_index=True
            )

        return converted_df

    def get(self, return_column, lookup_value):

        return self.df[return_column].iloc[
            self.df[self.df[self.main_key] == lookup_value].index[0]
        ]

    def print_df(self):

        print()
        print(self.df)

    def save_csv(self):

        t.save_df_to_csv(self.df, self.csv_name, neutrino.db_path)
