import neutrino
import neutrino.tools as t
import traceback

class Interface():
    
    def __init__(self, start=True):

        self.neutrino = neutrino.Neutrino(cbkey_set_name="default", from_database=True)
        
        if start:
            self.interact()

    def interact(self):
        """Temporary rudimentary command line interface that executes neutrino-related commands from user input. \
        The jankiness of this implementation and availability of modules such as ``argparse`` are well-understood. \
        This is mostly used for flexible testing/debugging during development.

        This function is wrapped in a ``while True`` block to execute an arbitrary number of commands \
        until terminated by the user.
        """

        # set verbosity to True to print outputs to console
        self.neutrino.set_verbosity(True)

        # continuously accept user input
        while True:

            try:

                print(neutrino.DIVIDER)

                # gather user input as a list of tokens
                arg = input("\n>>> ").split()

                # reload user settings (user can update settings file prior to providing a new command)
                self.neutrino.refresh_user_settings()

                # don't do anything if no input was provided
                if len(arg) == 0:
                    continue

                # TODO: get arg metadata (length, etc.)

                # exit the program if 'quit' or 'q' are entered
                if arg[0] in ("quit", "q"):
                    break

                # print list of available commands
                if arg[0] in ("help", "h"):
                    print(
                        "\n A printed list of available commands. Not yet implemented."
                    )

                # print n attributes/internal data
                if arg[0] in ("state"):
                    print(
                        "\n A summary of the Neutrino's Datum objects. Not yet implemented."
                    )

                # update cbkey_set_name used for authentication
                elif arg[0] == "cbkeys":

                    if len(arg) == 1:
                        print(
                            f"\n No keys provided. Please provide a value for cbkey_set_name."
                        )

                    # list the available cbkey names
                    elif arg[-1] == "-l":
                        print("\n Available API key sets:")
                        [print(f"   + {i}") for i in self.neutrino.cbkeys.keys()]

                    else:
                        self.neutrino.update_auth(self.neutrino.cbkeys.get(arg[1]))
                        print(f"\n API key set changed to: {arg[1]}")

                # parse 'get' statements
                elif arg[0] == "get":

                    # establish whether or not to export retrieved data to CSV,
                    # or whether or not to load data from CSV
                    save = True if arg[-1] == "-s" else False
                    from_database = True if arg[-1] == "-d" else False

                    # TODO: prompt user w/ list of acceptable values
                    if len(arg) == 1:
                        print(
                            f"\n No 'get' method provided. Please specify what should be retrieved."
                        )

                    elif arg[1] == "accounts":

                        # get account data
                        accounts = self.neutrino.generate_datum(
                            name="accounts",
                            from_database=from_database,
                        )

                        # filter to default filter_accounts filters if 'all' was not specified
                        if len(arg) <= 2 or arg[2] != "all":
                            self.neutrino.verbose = False
                            accounts.df = self.neutrino.filter_accounts(accounts.df)
                            self.neutrino.verbose = True

                        if save:
                            accounts.save_csv()

                        accounts.print_df()

                    elif arg[1] == "ledger":

                        # parse which currency for which to get the ledger - default to BTC if none given
                        if len(arg) > 2:
                            currency = arg[2]
                        else:
                            print("\n No currency provided - using BTC as default:")
                            currency = "BTC"

                        self.neutrino.get_account_ledger(
                            self.neutrino.accounts.get("id", currency, "currency"),
                            from_database=from_database,
                            save=save,
                        ).print_df()

                    elif arg[1] == "transfers":

                        self.neutrino.generate_datum(
                            name="transfers", from_database=from_database, save=save
                        ).print_df()

                    elif arg[1] == "orders":

                        # get the list of requested statuses from args
                        status = [i for i in arg[2:] if i not in ("-s", "-d")]

                        # if no statuses are requested, then default to 'all'
                        status = "all" if status == [] else status

                        self.neutrino.generate_datum(
                            name="orders",
                            from_database=from_database,
                            save=save,
                            status=status,
                        ).print_df()

                    elif arg[1] == "fees":
                        t.print_recursive_dict(self.neutrino.send_api_request("GET", "/fees")[0])

                    elif arg[1] == "candles":
                        self.neutrino.get_product_candles(
                            self.neutrino.user_settings.get("candles").get("product_id"),
                            granularity=self.neutrino.user_settings.get("candles").get(
                                "granularity"
                            ),
                            start=self.neutrino.user_settings.get("candles").get("start"),
                            end=self.neutrino.user_settings.get("candles").get("end"),
                            save=save,
                        )

                    elif arg[1] == "all":
                        print("\n TBD")

                    else:  # generic API/database request

                        self.neutrino.generate_datum(
                            name=arg[1],
                            from_database=from_database,
                            method="get",
                            endpoint=f"/{arg[1]}",
                            save=save,
                        ).print_df()

                # set Link verbosity
                elif arg[0] == "verbosity":

                    if len(arg) == 1:
                        print(
                            f"\n No verbosity option specified. Acceptable arguments are 'on' or 'off'."
                        )

                    elif arg[1] == "on":
                        self.neutrino.set_verbosity(True)

                    elif arg[1] == "off":
                        self.neutrino.set_verbosity(False)

                # stream data
                elif arg[0] == "stream":

                    # TODO: prompt user w/ list of acceptable values
                    if len(arg) < 2:
                        print(
                            f"\n Stream name not specified. Please specify a stream name."
                        )

                    # partially hard-code for now - in future, split into components, let user append items to lists, etc.
                    self.neutrino.configure_new_stream(
                        arg[1],
                        self.neutrino.user_settings.get("stream").get("product_ids"),
                        self.neutrino.user_settings.get("stream").get("channels"),
                    )

                    try:
                        self.neutrino.start_stream(arg[1])
                        self.neutrino.parse_stream_messages(arg[1])
                    # TODO: implement a cleaner way to kill a stream
                    except KeyboardInterrupt:
                        self.neutrino.stop_stream(arg[1])
                    # TODO: implement specific errors
                    except Exception as e:
                        if self.neutrino.streams.get(arg[1]).active:
                            self.neutrino.stop_stream(arg[1])
                        print(f"\n {e}")

                elif arg[0] == "update":

                    if arg[-1] == "-f":
                        self.neutrino.updater.update_neutrino(force=True)
                    else:
                        self.neutrino.updater.check_for_updates()

                else:
                    print("\n Unrecognized command or specification.")

            except Exception as exc:
                if exc == "\n Neutrino annihilated.":
                    break
                else:
                    print(
                        "\n ERROR: prototype interface has encountered the following exception:\n"
                    )
                    [print(f"   {i}") for i in traceback.format_exc().split("\n")]
        
        print("\n Neutrino annihilated.")
        print(neutrino.DIVIDER)