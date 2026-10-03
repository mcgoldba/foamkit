import foamkit.functions as pf
import warnings
import IPython
from IPython.terminal.prompts import Prompts, Token
from code import InteractiveConsole
import atexit
import os
import argparse
from configparser import ConfigParser
from foamkit import userMsg
from pathlib import Path
from traitlets.config import Config # for IPython config
# import config
import sys

import foamkit.types as pt

import logging
logger = logging.getLogger('foamkit')

class FoamKitConsole(InteractiveConsole):
    def __init__(*args, **kwargs):
        InteractiveConsole.__init__(*args, **kwargs)

class CommandLine:
    def __init__ (self, addArgs, configFilepath):
        self.configFilepath = configFilepath
        self.config = ConfigParser()
        self.config.read(configFilepath)
        self.prog = 'pf'
        self.addArgs = addArgs

    def init(self):
        """
        Read an OpenFOAM case and store as a Python dictionary.
        """
        self.prog+= ' init'

        parser = argparse.ArgumentParser(prog=self.prog)

        parser.add_argument('-path',type=str, nargs='?',
                            help='The path of the OpenFOAM case to parse.')

        args = parser.parse_args(self.addArgs)
        
        if args.path is None:
            case = pf.init()
        else:
            case = pf.init(path=args.path)

        logger.debug(f"case: {case}")

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

        #TODO:  Is this method loading a case multiple times?

        self.prog+= ' edit'

        parser = argparse.ArgumentParser(prog=self.prog)

        parser.add_argument('-ipython',type=bool, nargs=1, default=True,
                            help='If `True`, starts an IPython console instead \
                                of a Python console.')

        parser.add_argument('-path',type=str, nargs='?',
                            help='The path of the OpenFOAM case to parse.')

        args = parser.parse_args(self.addArgs)

        # import foamkit.functions as pf
        # import foamkit.types as pt
        # try:
        #     case = pf.load()
        # except FileNotFoundError:
        #     userMsg("No cached case data found.  Run 'pf init'"\
        #     " before 'pf edit'.", "WARNING")
        #     case = None

        case = pf.load()

        #TODO:  Automatically save case before exiting or maybe automatically
        #          save case everytime the ofCase is modified?
        if args.ipython:

            c = Config()
            c.TerminalInteractiveShell.confirm_exit = False
            c.TerminalIPythonApp.display_banner = False
            c.InteractiveShellApp.exec_files = [
                str(Path(__file__).parent /  '_iPython_env.py')
            ]

            # IPython.embed(header="", config=c, prompt=FoamKitPrompt)
            IPython.start_ipython(argv=[], config=c)

            logger.debug(f"case: {case}")
            # if case is not None:
            #     # pf.writeParams(case, '_case.json')
            #     # pf.writeCase(case)
            #     case.save()
        else:  # Use a customized version of the standard Python console
            
            def atExitCommands():
                try:
                    print("Saving case to FoamKit cache (i.e. as a JSON object)")
                    print(locals())
                    locals()['case'].save()
                finally:
                    sys.exit()
            
            # atexit.register(atExitCommands)

            exit = atExitCommands

            #exit = atExitCommands



            # namespace = {'case':case}
            console = FoamKitConsole(locals=dict(globals(), **locals()))
            console.interact()

            atexit.unregister(atExitCommands)


    def setConfig(self):
        """
        Set details of the FoamKit configuration, specified in 'config.ini'
        """
        self.prog+= ' setConfig'

        parser = argparse.ArgumentParser(prog=self.prog)

        parser.add_argument('key',type=str, nargs=1,
                            help='The configuration variable to be set.')
    
        parser.add_argument('value', nargs=1,
                        help='The value to which the variable is to be set.')

        args = parser.parse_args(self.addArgs)

        if 'user' in self.config.keys():
            self.config['user'].update({args.key[0]: args.value[0]})
        else:
            self.config['user'] = {args.key[0]: args.value[0]}

        with open(self.configFilepath, 'w') as configFile:
            self.config.write(configFile)

        userMsg(f"Setting '{args.key[0]}' config option" 
            f" to '{args.value[0]}'.", "INFO")
    
    def write(self):
        """
        Save the case, and overwrite the existing OpenFOAM dictionary case with 
        values in the `ofCase`.  Saves existing case structure in cache for 
        backup.
        """
        self.prog+= ' write'

        parser = argparse.ArgumentParser(prog=self.prog)



        parser.add_argument('-path',type=str, nargs='?',
                            help='The path of the OpenFOAM case to parse.')

        args = parser.parse_args(self.addArgs)

        if args.path is None: 
            case = pf.load()
        else:
            logger.debug("Parsing with args.")
            case = pf.load(path=args.path)
        
        case.write()

    def plot(self):
        self.prog+= ' plot'

        parser = argparse.ArgumentParser(prog=self.prog)

        parser.add_argument('values', type=str, nargs='+', 
                            default=['U', 'p', 'residuals'],
                            help='Log files to monitor')

        parser.add_argument('-casePath',type=str, nargs='1',
                            default = Path.cwd(),
                            help='The path of the OpenFOAM case to parse.')


        args = parser.parse_args(self.addArgs)

        for value in args.values:
            try:
                monitor = pf.getProbe(value, workingDir=args.workingDir)
            except FileNotFoundError:
                monitor = pf.getMonitor(value, workingDir=args.workingDir)

            pf.plot(monitor=monitor)


    def monitor(self):
        self.prog+= ' monitor'

        parser = argparse.ArgumentParser(prog=self.prog)

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
            userMsg("`yrange` argument must be length two.")

        pf.monitor(value=args.value[0], workingDir=args.casePath, 
                    filter=args.filter, yrange=args.yrange, 
                    logScale = args.log, time = args.time)

    def cloneCase(self):
        self.prog+=' cloneCase'

        parser = argparse.ArgumentParser(prog=self.prog)

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

        args = parser.parse_args(self.addArgs)

        pf.cloneCase(args.src, args.dest, sshSrc=args.sshSrc, 
            sshDest=args.sshDest, includeTriSurface=args.includeTriSurface)
    
    def cloneCases(self):
        self.prog += ' cloneCases'

        parser = argparse.ArgumentParser(
            prog=self.prog,
            description="Clone all cases found in the srcPath to destPath"
            )

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

        args = parser.parse_args(self.addArgs)

        pf.cloneCases(args.src, args.dest, sshSrc=args.sshSrc, 
            sshDest=args.sshDest, includeTriSurface=args.includeTriSurface)

