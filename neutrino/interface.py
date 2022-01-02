import traceback

DIVIDER = (
    "\n -------------------------------------------------------------------------------"
)


def interact(neutrino):
    """Temporary rudimentary command line interface that executes Neutrino-related commands from user input. \
    The jankiness of this implementation and availability of modules such as ``argparse`` are well-understood. \
    This is mostly used for highly flexible testing/debugging during development.

    This function is wrapped in a ``while True`` block to execute an arbitrary number of commands \
    until terminated by the user.

    Further documentation TBD.

    Args:
        neutrino (Neutrino): An initialized :py:obj:`Neutrino<neutrino.main.Neutrino>` object.
    """

    # set verbosity to True to print outputs to console
    neutrino.set_verbosity(True)

    # continuously accept user input
    while True:

        try:

            print(DIVIDER)

            # gather user input as a list of tokens
            arg = input("\n>>> ").split()

            # reload user settings (user can update settings file prior to providing new command)
            neutrino.refresh_user_settings()

            # don't do anything if no input was provided
            if len(arg) == 0:
                continue

            # TODO: get arg metadata (length, etc.)

            # exit the program if 'quit' or 'q' are entered
            if arg[0] in ("quit", "q"):
                break

            # print list of available commands
            if arg[0] in ("help", "h"):
                print("\n Help coming soon.")

            # print neutrino attributes/internal data
            if arg[0] in ("state"):
                print("\n State coming soon.")

            # update cbkey_set used for authentication
            elif arg[0] == "cbkeys":

                # TODO: display default value and prompt user to accept or override this default w/ list of acceptable values
                if len(arg) == 1:
                    print(
                        f"\n No keys provided. Please provide a value for cbkey_set_name."
                    )

                else:
                    neutrino.update_auth(arg[1])
                    print(f"\n Neutrino authentication keys changed to: {arg[1]}")

            # parse 'get' statements
            elif arg[0] == "get":

                # establish whether or not to export retrieved data to CSV
                save = True if arg[-1] == "-s" else False
                from_database = True if arg[-1] == "-d" else False

                # TODO: prompt user w/ list of acceptable values
                if len(arg) == 1:
                    print(
                        f"\n No 'get' method provided. Please specify what should be retrieved."
                    )

                elif arg[1] == "accounts":
                    neutrino.get_accounts(save=save, from_database=from_database)

                elif arg[1] == "ledger":

                    if len(arg) > 2:
                        currency = arg[2]
                    else:
                        print("\n No currency provided - using BTC as default:")
                        currency = "BTC"

                    neutrino.retrieve_account_ledger(
                        neutrino.accounts.get(currency).get("id"), save=save
                    )

                elif arg[1] == "transfers":
                    neutrino.get_transfers(save=save, from_database=from_database)

                elif arg[1] == "orders":

                    if len(arg) > 2:
                        if not save and not from_database:
                            neutrino.get_orders(save=save, status=arg[2:])
                        else:
                            neutrino.get_orders(
                                save=save, from_database=from_database, status=arg[2:-1]
                            )
                    else:
                        neutrino.get_orders()

                elif arg[1] == "fees":
                    neutrino.get_fees()

                elif arg[1] == "candles":
                    neutrino.get_product_candles(
                        neutrino.user_settings.get("candles").get("product_id"),
                        granularity=neutrino.user_settings.get("candles").get(
                            "granularity"
                        ),
                        start=neutrino.user_settings.get("candles").get("start"),
                        end=neutrino.user_settings.get("candles").get("end"),
                        save=save,
                    )

                elif arg[1] == "all":
                    neutrino.get_all_link_data(save=save)

                else:
                    print(f"\n Unrecognized 'get' method: {arg[1]}")

            # set Link verbosity
            elif arg[0] == "verbosity":

                # hard-code for now - this is a temporary proof-of-concept
                if len(arg) == 1:
                    print(
                        f"\n No verbosity option specified. Acceptable arguments are 'on' or 'off'."
                    )

                elif arg[1] == "on":
                    neutrino.set_verbosity(True)

                elif arg[1] == "off":
                    neutrino.set_verbosity(False)

                else:
                    print(f"\n Unrecognized verbosity specification: {arg[1]}")

            # stream data
            elif arg[0] == "stream":

                # TODO: prompt user w/ list of acceptable values
                if len(arg) < 2:
                    print(
                        f"\n Stream name not specified. Please specify a stream name."
                    )

                # partially hard-code for now - in future, split into components, let user append items to lists, etc.
                neutrino.configure_new_stream(
                    arg[1],
                    neutrino.user_settings.get("stream").get("product_ids"),
                    neutrino.user_settings.get("stream").get("channels"),
                )

                try:
                    neutrino.start_stream(arg[1])
                    neutrino.parse_stream_messages(arg[1])
                # TODO: implement a cleaner way to kill a stream
                except KeyboardInterrupt:
                    neutrino.stop_stream(arg[1])
                # TODO: implement specific errors
                except Exception as e:
                    if neutrino.streams.get(arg[1]).active:
                        neutrino.stop_stream(arg[1])
                    print(f"\n {e}")

            elif arg[0] == "update":

                if arg[-1] == "-f":
                    neutrino.update_neutrino(check_completed=True)
                else:
                    neutrino.update_neutrino()

            else:
                print("\n Unrecognized command.")

        except Exception as exc:
            if exc == "\n Neutrino annihilated.":
                break
            else:
                print(
                    "\n ERROR: prototype interface has encountered the following exception:\n"
                )
                traceback.print_exc()
