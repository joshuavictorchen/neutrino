import neutrino.config as c
import neutrino.tools as t


class Datum:
    """Custom data object that contains a DataFrame and a corresponding main key \
        with which to pull specific DataFrame values.
    
    .. note::

        This class may be used to do more useful things in the future.

    **Instance attributes:** \n
        * **name** (*str*): Name of the Datum.
        * **df** (*DataFrame*): The Datum's DataFrame object, where data is stored.
        * **main_key** (*str*): Name of the main (unique) key column of the Datum's DataFrame.

    Args:
        name (str): Name of the :py:obj:`Datum` to be generated. Used as the default filename when exporting data to CSV.
        df (DataFrame): DataFrame object for the Datum.
        main_key (str): Name of the main (unique) key column of the provided DataFrame.\
            Used to retrieve values from the DataFrame in a similar manner to a dictionary.
        save (bool, optional): Exports the DataFrame's data as a CSV to the default database path if ``True``. Defaults to ``False``.
    """

    def __init__(self, name, df, main_key, save=False):

        self.name = name
        self.df = df

        # if the provided main_key is none, then default to 'id':
        if main_key is None:
            main_key = "id"
            print(f"\n WARNING: no main key for {name} found; defaulting to 'id'")

        self.main_key = main_key

        if save:
            self.save_csv()

    def get(self, return_column, lookup_value, lookup_key=None):
        """Treats the :py:obj:`self.df` DataFrame as a dictionary and pulls the value of ``return_column`` corresponding to \
            the row containing ``lookup_value`` within the ``lookup_key`` column.

        .. admonition:: TODO

            Throw a warning/error if the key is not unique, doesn't exist, etc. Currently, the first matching value is returned \
            if multiple matches exist.

        Args:
            return_column (str): Column of the value to be returned.
            lookup_value (str): Value of the key to look up.
            lookup_key (str, optional): Column of the key to look up. Defaults to :py:obj:`self.main_key`.

        Returns:
            various: Value of the ``return_column`` corresponding to the lookup inputs.
        """

        # TODO: throw warning if key is not unique, doesn't exist, etc.

        if lookup_key is None:
            lookup_key = self.main_key

        return self.df[return_column].iloc[
            self.df[self.df[lookup_key] == lookup_value].index[0]
        ]

    def print_df(self):
        """Simply prints :py:obj:`self.df` to the console with a leading newline."""

        print()
        print(self.df)

    def save_csv(self, custom_name=None, custom_dir=None):
        """Exports :py:obj:`self.df` to a CSV file via :py:obj:`neutrino.tools.save_df_to_csv`.\
            The CSV name and filepath may be specified.

        Args:
            custom_name (str, optional): Name of the CSV file to be saved. Defaults to :py:obj:`self.name`.
            custom_dir (str, optional): Path to where the CSV file will be saved.\
                Defaults to the :py:obj:`neutrino.main.Neutrino`'s ``db_path``.
        """

        csv_name = custom_name if custom_name else self.name
        database_path = custom_dir if custom_dir else c.db_path

        t.save_df_to_csv(self.df, csv_name, database_path)
