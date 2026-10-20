import sys
import argparse, textwrap
from importlib.metadata import version as _distVersion
from foamkit import getFoamKitConfig, setLoggerLevel, enableRichTracebacks, \
    FoamKitError

from foamkit.commandline import CommandLine

from pathlib import Path
from rich import print
from rich.markup import escape
import logging

logger = logging.getLogger('foamkit')

#- Commands, mapped to the `CommandLine` method that runs them
COMMANDS = ('init', 'edit', 'setConfig', 'write', 'plot', 'monitor',
            'cloneCase', 'cloneCases')

#- main() function
def main():
    """
    FoamKit:  A Pythonic interface to OpenFOAM.
    """

    #- Application entry point: it is fine (and expected) to configure
    #- logging and tracebacks here, but never at import time in the library.
    logging.basicConfig(level=logging.INFO)
    enableRichTracebacks()

    version = _distVersion("foamkit")

    intro = "\n"+main.__doc__.strip()+"\nversion "+version + \
            " on Python "+str(sys.version_info.major)+"."+\
                    str(sys.version_info.minor)+"."+\
                    str(sys.version_info.micro)+'\n'

    print("[bold grey35]"+intro)

    if Path(sys.argv[0]).stem == 'pf':
        print("[bold orange]WARNING:[/bold orange] The 'pf' command is "
              "deprecated and will be removed; use 'fk' instead.\n")

    parser = argparse.ArgumentParser(prog = 'fk')

    #- parse args manually to find command args: everything after the command
    #  is passed to the command's own parser.
    args=sys.argv
    i = 0
    while args[i] not in COMMANDS:
        i += 1
        if i >=len(args):
            parser.print_help()
            sys.exit()

    opt_args = args[1:i]
    addArgs = args[i:]

    cl = CommandLine(addArgs[1:])
    commands = {command: getattr(cl, command) for command in COMMANDS}

    parser.add_argument(
        'command',
        help=textwrap.dedent("The command to be executed."),
        choices=commands.keys()
    )

    args = parser.parse_args(opt_args+[addArgs[0]])

    debug = getFoamKitConfig('debug')

    setLoggerLevel("DEBUG" if debug else "INFO")

    logger.debug("debug: %s", debug)
    logger.debug("main args: %s", opt_args+[addArgs[0]])
    logger.debug("main addArgs: %s", addArgs)

    try:
        commands[addArgs[0]]()
    except FoamKitError as e:
        #- `userMsg` has already shown its message; print only if it did not.
        if not e.reported:
            print(f"[bold red]ERROR:[/bold red] {escape(e.msg)}")
        sys.exit(1)

    print("")

if __name__ == '__main__':
    main()
