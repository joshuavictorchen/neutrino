import neutrino
import neutrino.tools as t


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

    def __init__(self, name, df, main_key, origin, save=False):

        self.name = name
        self.df = df
        self.main_key = main_key
        self.origin = origin

        if save:
            self.save_csv()

    def get(self, return_column, lookup_value, lookup_key=None):

        # TODO: throw warning if key is not unique, doesn't exist, etc.

        if lookup_key is None:
            lookup_key = self.main_key

        return self.df[return_column].iloc[
            self.df[self.df[lookup_key] == lookup_value].index[0]
        ]

    def print_df(self):

        print()
        print(self.df)

    def save_csv(self, custom_name=None, custom_dir=None):

        csv_name = custom_name if custom_name else self.name
        database_path = custom_dir if custom_dir else neutrino.db_path

        t.save_df_to_csv(self.df, csv_name, database_path)
