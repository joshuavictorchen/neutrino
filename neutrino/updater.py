import git
import neutrino.config as c
import neutrino.tools as t
import os
import subprocess
import sys
import traceback


class Updater:
    """Checks for updates to the neutrino repository. Implements them and handles pip installs as applicable.

    **Instance attributes:** \n
        * **repo** (:py:obj:`git.Repo`): Object representing the local neutrino repository.

    Args:
        print (bool): Prints the repo's metadata to the console upon instantiation if ``True``. Defaults to ``True``.
        check (bool): Checks for repo updates upon instantiation if ``True``. Defaults to ``True``.
    """

    def __init__(self, print=True, check=True):

        self.retrieve_repo()

        if print:
            self.print_repo()

        if check:
            self.check_for_updates()

    def retrieve_repo(self):
        """Retrieves metadata on the local neutrino repository. Optionally prints to the console via :py:obj:`print_repo`.

        Returns:
            Repo: :py:obj:`git.Repo` object representing the local neutrino repository.
        """

        # instantiate a repo object for the neutrino repository
        self.repo = git.Repo(
            f"{os.path.abspath(__file__)}", search_parent_directories=True
        )

        return self.repo

    def check_for_updates(self):
        """Performs a ``git fetch`` command to check for updates to the current branch of the repository.

        If updates exist, then prompts the user to execute :py:obj:`Neutrino.update_neutrino`.

        Returns:
            bool: ``True`` if updates are available.
        """

        print("\n Checking for updates...", end="")
        self.repo.remotes.origin.fetch()
        updates_available = False

        # if head is in detached state, then return with no updates
        if self.repo.head.is_detached:
            print(" repo's HEAD is detached.")
            return updates_available

        # check for newer commits
        if (
            sum(
                1
                for i in self.repo.iter_commits(
                    f"{self.repo.active_branch.name}..origin/{self.repo.active_branch.name}"
                )
            )
            > 0
        ):
            updates_available = True

        if updates_available:
            update = input(
                " updates are available. \
                \n\n Press [enter] to update the neutrino. Input any other key to continue without updating: "
            )
            if update == "":
                self.update_neutrino(force=True)
                sys.exit()
        else:
            print(" the neutrino is up to date.")

        return updates_available

    def update_neutrino(self, force=False):
        """Performs the following actions to update the neutrino program:

            1. Checks for updates. If no updates are available, the function is exited.
            2. Performs a ``git pull`` if updates are available.
            3. Checks ``\\internals\\update-info.yaml`` to see if a ``pip install`` is required.
            4. If required, prompts the user to approve the ``pip install`` action.
            5. If approved, performs the ``pip install`` action.
            6. Displays the change summary from ``\\internals\\update-info.yaml``.
            7. Exits the program, which must be restarted for the changes to take effect.

        Args:
            force (bool, optional): Skips step 1 (above) if set to ``True``. Defaults to ``False``.
        """

        # check for updates, unless updates have already been checked for, or a force update has been specified
        if not force:
            self.check_for_updates()
            return

        try:
            # git pull
            self.repo.remotes.origin.pull()

            # git submodule update --init
            for submodule in self.repo.submodules:
                submodule.update(init=True)

            # get update metadata
            update_info = t.parse_yaml(
                c.root_dir / "internals/update-info.yaml", echo_yaml=False
            )

            print(f"\n Updates pulled - change summary:\n")
            for i in update_info.get("changelog"):
                print(f"   + {i}")

            self.print_repo()

            # if a pip install is required for this update, then do a pip install
            # remember to switch to the root directory first, then switch back after
            # NOTE: permissions issues arise during setup if the user is in a venv
            #       if the user is in a venv, then prompt them to execute the pip install command manually
            if update_info.get("pip_install"):
                print(c.DIVIDER)
                print("\n A pip install is required to complete this update.")
                if os.environ.get("VIRTUAL_ENV") is not None:
                    input(
                        f" Since you are in a venv, the following command must be executed manually: \
                        \n\n   pip install -U -e . \
                        \n\n Press [enter] or input any key to acknowledge: "
                    )
                else:
                    pip_install = input(
                        f"\n Press [enter] to perform this installation. Input any other key to decline: "
                    )
                    if pip_install == "":
                        print()
                        this_dir = os.getcwd()
                        os.chdir(c.root_dir)
                        subprocess.call("pip install -U -e . --user")
                        os.chdir(this_dir)
                    else:
                        print(
                            f"\n WARNING: pip install not performed - some dependencies may be missing."
                        )

        except Exception:
            print(f"\n Error during self-update process:\n")
            [print(f"   {i}") for i in traceback.format_exc().split("\n")]
            sys.exit(
                " Self-update cancelled. Please check your repository configuration and/or try a manual update."
            )

        sys.exit("\n Neutrino annihilated.")

    def print_repo(self):
        """Prints information about the current state of :py:obj:`self.repo`'s repository in the following form:

        ``n | {branch}-{commit}`` if the repository is clean

        ``n | {branch}-{commit}-modified`` if the repository is dirty
        """

        # get repo attributes
        branch_name = self.repo.active_branch.name
        commit_id = self.repo.head.object.hexsha[:7]
        is_dirty = self.repo.is_dirty(untracked_files=True)

        # format output
        output = f"\n n | {branch_name}-{commit_id}"
        if is_dirty:
            output += "-modified"

        print(output)
