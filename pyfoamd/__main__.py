import sys
import argparse, textwrap
from argparse import RawTextHelpFormatter
from importlib.metadata import version as _distVersion
#import resource
import os
from pyfoamd import getPyFoamdConfig, setLoggerLevel, enableRichTracebacks
import pyfoamd.functions as pf
from pathlib import Path

from pyfoamd.commandline import CommandLine

# from pyfoamd.config import DEBUG, DICT_FILESIZE_LIMIT

from rich import print
import logging

logger = logging.getLogger('pf')
# from rich.logging import RichHandler

# FORMAT = "%(message)s"
# logging.basicConfig(
#        level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
# )

# logger= logging.getLogger("pf")

# from rich.traceback import install
# install()

# from .richinclude import richLogger

#- main() function
def main():
    """
    PyFoamd:  Pythonic manipulation of OpenFOAM dictionaries.
    """

    #- Application entry point: it is fine (and expected) to configure
    #- logging and tracebacks here, but never at import time in the library.
    logging.basicConfig(level=logging.INFO)
    enableRichTracebacks()

    version = _distVersion("pyfoamd")

    intro = "\n"+main.__doc__.strip()+"\nversion "+version + \
            " on Python "+str(sys.version_info.major)+"."+\
                    str(sys.version_info.minor)+"."+\
                    str(sys.version_info.micro)+'\n'

    print("[bold grey35]"+intro)

    #- Increase memory allocation and recusion depth
    # resource.setrlimit(resource.RLIMIT_STACK, 
    #     (getPyFoamdConfig('stack_size'),resource.RLIM_INFINITY))
    # sys.setrecursionlimit(10**6)

    # #- Manually capture the "help" arguments and process last
    # help = None
    # args = sys.argv
    # for i in range(len(sys.argv)):
    #     if any([sys.argv[i] == h for h in ['-h', '--help']]) is True:
    #         help = i
    #         args = sys.argv[:i]
    #         break

    #- Argument parser
    parser = argparse.ArgumentParser(
        prog = 'pf',
        # description=main.__doc__
        # formatter_class=argparse.RawTextHelpFormatter,
    )

    #subparsers = parser.add_subparsers()

    commands = {
        'init': None, #- `None` values to be updated after extracting `addArgs`
        'edit': None,   
        'setConfig': None,
        'write': None,
        'plot': None,
        'monitor': None,
        'cloneCase': None,
        'cloneCases': None
    }

    # commandsStr = ''
    # i=0
    # while i<len(commands.keys()):
    #     commandsStr += list(commands.keys())[i]+', '
    #     if len(commandsStr.split('\n')[-1]) > 70:
    #         commandsStr+= '\n'
    #     i+=1
    #
    # commandsStr = commandsStr.rstrip(', ')

    #- parse args manually to find command args
    args=sys.argv
    i = 0
    while any([c == args[i] for c in commands]) is False:
        i += 1
        if i >=len(args):
            parser.print_help()
            sys.exit()

    opt_args = args[1:i]
    addArgs = args[i:]

    # #- Manually parse the optional arguments
    # debug = False
    # for i in range(len(opt_args)):
    #     if opt_args[i] == '--debug':
    #         debug = True
    #         i+=1

    #     elif any([opt_args[i] == command for command in commands.keys()]):
    #         break

    #- Update commands that require `addArgs`
    cl = CommandLine(addArgs[1:],  Path(__file__).parent / 'config.ini')
    commands['init'] = cl.init
    commands['edit'] = cl.edit
    commands['setConfig'] = cl.setConfig
    commands['write'] = cl.write
    commands['plot'] = cl.plot
    commands['monitor'] = cl.monitor
    commands['cloneCase'] = cl.cloneCase
    commands['cloneCases'] = cl.cloneCases

    commandsStr = ''

    for command in commands.keys():
        commandsStr+= '{0:<30}'.format(command+":")
        if commands[command].__doc__:
            commandsStr+= commands[command].__doc__+'\n\n'
        else:
            commandsStr+= '\n\n'


    parser.add_argument(
        'command',
        # metavar='command',
        # help=textwrap.dedent("The command to be executed.  Valid commands are:\n\n"+commandsStr),
        help=textwrap.dedent("The command to be executed."),
        choices=commands.keys()
    )

    #- Global [<options>] arguments

    # parser.add_argument('--debug',
    #                     help="Print out additional debug information",
    #                     action='store_true'
    #                    )




    args = parser.parse_args(opt_args+[addArgs[0]])

    debug = getPyFoamdConfig('debug')

    setLoggerLevel("DEBUG" if debug else "INFO")

    logger.debug(f"debug: {debug}")

    #logger.setLevel("DEBUG" if debug else "INFO")

    logger.debug('main args:'+str(opt_args+[addArgs[0]]))
    logger.debug('main addArgs:'+str(addArgs))

    # commandList = list(commands.keys())


    # cl = CommandLine(addArgs[1:])

    # CL_FUNCTION_MAP = {
    #     commandList[0]: cl.init,
    # }

    # cl_func = CL_FUNCTION_MAP[addArgs[0]]
    cl_func = commands[addArgs[0]]
    cl_func()

    print("")

if __name__ == '__main__':
    main()