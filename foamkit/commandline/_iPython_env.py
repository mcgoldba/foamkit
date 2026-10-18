import os
import IPython
from IPython.terminal.prompts import Prompts, Token
import foamkit.functions as pf
import foamkit.types as pt
from foamkit.commandline import EDIT_PATH_ENV

#- `pf edit -path <case>` passes the case path through the environment
case = pf.load(os.environ.get(EDIT_PATH_ENV))

class FoamKitPrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, 'pf edit>>')]

    def out_prompt_tokens(self):
        return []

ip = IPython.get_ipython()

#TODO: Find a way to automatically save the case when exiting IPython.
# ref: https://stackoverflow.com/a/39502890/10592330

#- Allow for calls to sys.exit()
# ref: https://stackoverflow.com/a/1528023/10592330
type(exit).__repr__ = lambda s: setattr(s.shell, 'exit_now', True) or ''

ip.prompts = FoamKitPrompt(ip)
