import IPython
from IPython.terminal.prompts import Prompts, Token
import foamkit.functions as pf
import foamkit.types as pt
# import atexit
import sys

case = pf.load()

class FoamKitPrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, 'pf edit>>')]

    def out_prompt_tokens(self):
        return []

ip = IPython.get_ipython()

#TODO: Find a way to automatically save the case when exiting IPython.
# ref: https://stackoverflow.com/a/39502890/10592330
# class FoamKitQuitter:
#     def __repr__(self):
#         print("Saving case to FoamKit cache (i.e. as a JSON object)")
#         exec("case.save()")
        # exec("sys.exit()")



#- Allow for calls to sys.exit()
# ref: https://stackoverflow.com/a/1528023/10592330
type(exit).__repr__ = lambda s: setattr(s.shell, 'exit_now', True) or ''

#- Save the case before exiting:
# ref: https://stackoverflow.com/a/39502890/10592330
#atexit.register(atExitCommands)

# exit = FoamKitQuitter()

ip.prompts = FoamKitPrompt(ip)