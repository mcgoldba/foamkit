import foamkit.functions as pf
import IPython
from code import InteractiveConsole
import os
import argparse
from configparser import ConfigParser
from foamkit import userMsg, USER_CONFIG
from pathlib import Path
from traitlets.config import Config # for IPython config

import foamkit.types as pt

import logging
logger = logging.getLogger('foamkit')

#- Environment variable used to pass `fk edit -path` to the IPython startup file
EDIT_PATH_ENV = 'FOAMKIT_EDIT_PATH'


def _strToBool(value):
    """argparse type for boolean option values (e.g. `-ipython False`)."""
    if isinstance(value, bool):
        return value
    if value.lower() in ('1', 'yes', 'true', 'on'):
        return True
    if value.lower() in ('0', 'no', 'false', 'off'):
        return False
    raise argparse.ArgumentTypeError(f"Expected a boolean value, got '{value}'.")


class CommandLine:
    def __init__ (self, addArgs, configFilepath=None):
        #- `fk setConfig` writes to the per-user config, which takes
        #  precedence over the config shipped with the package (writing into
        #  the installed package would need write access and is lost on
        #  upgrade).
        self.configFilepath = Path(configFilepath) if configFilepath else USER_CONFIG
        self.prog = 'fk'
        self.addArgs = addArgs

    def _parser(self, command, **kwargs):
        self.prog += ' '+command
        return argparse.ArgumentParser(prog=self.prog, **kwargs)

    @staticmethod
    def _addPathArg(parser):
        parser.add_argument('-path',type=str, nargs='?',
                            help='The path of the OpenFOAM case to parse.')

    @staticmethod
    def _addCloneArgs(parser):
        parser.add_argument('src', type=str,
                            help='The case to clone.')

        parser.add_argument('dest', type=str,
                            help='The loction to clone the case to.')

        parser.add_argument('-sshSrc',type=str, nargs='?',
                            default = None,
                            help="If copying from a remote location, the string "
                            "of login details for the remote host in ssh format "
                            "(e.g. 'marc@my.remote.com')")

        parser.add_argument('-sshDest',type=str, nargs='?',
                    default = None,
                    help="If copying to a remote location, the string "
                    "of login details for the remote host in ssh format "
                    "(e.g. 'marc@my.remote.com')")

        parser.add_argument('-includeTriSurface',
            action='store_true',
            help="Copy files located in the '<case>/constant/triSurface' directory."
            )

    def init(self):
        """
        Read an OpenFOAM case and store as a Python dictionary.
        """
        parser = self._parser('init')
        self._addPathArg(parser)
        args = parser.parse_args(self.addArgs)

        if args.path is None:
            case = pf.init()
        else:
            case = pf.init(path=args.path)

        logger.debug("case: %s", case)

        #- store the case data as json file:
        if case is not None:
            if args.path is None:
                case.save()
            else:
                case.save(path=args.path)

    def edit(self):
        """
        Edit the case contents with an interactive (IPython) console.

        Console automatic imports:
            `import foamkit.functions as pf`
            `import foamkit.types as pt`
            `case = pf.load()`

        """
        parser = self._parser('edit')

        parser.add_argument('-ipython', type=_strToBool, nargs='?', const=True,
                            default=True,
                            help='If `True`, starts an IPython console instead '
                                'of a Python console.')

        self._addPathArg(parser)

        args = parser.parse_args(self.addArgs)

        #TODO:  Automatically save case before exiting or maybe automatically
        #          save case everytime the ofCase is modified?
        if args.ipython:
            #- The case is loaded (once) by the IPython startup file.
            if args.path is not None:
                os.environ[EDIT_PATH_ENV] = str(args.path)

            c = Config()
            c.TerminalInteractiveShell.confirm_exit = False
            c.TerminalIPythonApp.display_banner = False
            c.InteractiveShellApp.exec_files = [
                str(Path(__file__).parent /  '_iPython_env.py')
            ]

            IPython.start_ipython(argv=[], config=c)
        else:  # Use the standard Python console
            case = pf.load() if args.path is None else pf.load(path=args.path)
            console = InteractiveConsole(
                locals=dict(globals(), pf=pf, pt=pt, case=case))
            console.interact()

    def setConfig(self):
        """
        Set details of the FoamKit configuration, specified in 'config.ini'
        """
        parser = self._parser('setConfig')

        parser.add_argument('key',type=str, nargs=1,
                            help='The configuration variable to be set.')

        parser.add_argument('value', nargs=1,
                        help='The value to which the variable is to be set.')

        args = parser.parse_args(self.addArgs)

        config = ConfigParser()
        config.read(self.configFilepath)

        if 'user' in config.keys():
            config['user'].update({args.key[0]: args.value[0]})
        else:
            config['user'] = {args.key[0]: args.value[0]}

        self.configFilepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.configFilepath, 'w') as configFile:
            config.write(configFile)

        userMsg(f"Setting '{args.key[0]}' config option"
            f" to '{args.value[0]}' in {self.configFilepath}.", "INFO")

    def write(self):
        """
        Save the case, and overwrite the existing OpenFOAM dictionary case with
        values in the `ofCase`.  Saves existing case structure in cache for
        backup.
        """
        parser = self._parser('write')
        self._addPathArg(parser)
        args = parser.parse_args(self.addArgs)

        if args.path is None:
            case = pf.load()
        else:
            logger.debug("Parsing with args.")
            case = pf.load(path=args.path)

        case.write()

    def plot(self):
        """
        Plot probe or function object data from the 'postProcessing' directory.
        """
        parser = self._parser('plot')

        parser.add_argument('values', type=str, nargs='+',
                            default=['U', 'p', 'residuals'],
                            help='Log files to monitor')

        parser.add_argument('-casePath',type=str, nargs='?',
                            default = Path.cwd(),
                            help='The path of the OpenFOAM case to parse.')

        args = parser.parse_args(self.addArgs)

        for value in args.values:
            try:
                monitor = pf.getProbe(value, workingDir=args.casePath)
            except FileNotFoundError:
                monitor = pf.getMonitor(value, workingDir=args.casePath)

            pf.plot(monitor=monitor)

    def monitor(self):
        """
        Plot a probe or function object monitor, updating as data is written.
        """
        parser = self._parser('monitor')

        parser.add_argument('value', type=str, nargs=1, default='residual',
                            help='log file to monitor')

        parser.add_argument('-casePath',type=str, nargs='?',
                            default = Path.cwd(),
                            help='The path of the OpenFOAM case to parse.')

        parser.add_argument('-filter',type=str, nargs='?',
                            help='Filter the probe value to only monitor those '
                            'that match the regex string argument.')

        parser.add_argument('-yrange',type=float, nargs='*',
                            help='The limits of the y-axis for the monitor.')

        parser.add_argument('-log', action='store_true',
                                help='If `True`, y-axis is plotted with a log '
                                'scale.')

        parser.add_argument('-time', type=str, nargs='?', default = 'latestTime',
                                help='The postprocessing startTime to monitor')


        args = parser.parse_args(self.addArgs)

        if args.yrange is not None and len(args.yrange) != 2:
            userMsg("`yrange` argument must be length two.", "ERROR")

        pf.monitor(value=args.value[0], workingDir=args.casePath,
                    filter=args.filter, yrange=args.yrange,
                    logScale = args.log, time = args.time)

    def cloneCase(self):
        """
        Clone the setup files of an OpenFOAM case (no mesh or results).
        """
        parser = self._parser('cloneCase')
        self._addCloneArgs(parser)
        args = parser.parse_args(self.addArgs)

        pf.cloneCase(args.src, args.dest, sshSrc=args.sshSrc,
            sshDest=args.sshDest, includeTriSurface=args.includeTriSurface)

    def cloneCases(self):
        """
        Clone all cases found in the srcPath to destPath.
        """
        parser = self._parser('cloneCases',
            description="Clone all cases found in the srcPath to destPath")
        self._addCloneArgs(parser)
        args = parser.parse_args(self.addArgs)

        pf.cloneCases(args.src, args.dest, sshSrc=args.sshSrc,
            sshDest=args.sshDest, includeTriSurface=args.includeTriSurface)
