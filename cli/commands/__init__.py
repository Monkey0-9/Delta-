"""
Modular slash command handlers
"""

from delta.cli.commands.cmd_help import CommandHelp
from delta.cli.commands.cmd_model import CommandModel
from delta.cli.commands.cmd_auth import CommandAuth
from delta.cli.commands.cmd_broker import CommandBroker
from delta.cli.commands.cmd_news import CommandNews
from delta.cli.commands.cmd_macro import CommandMacro
from delta.cli.commands.cmd_track import CommandTrack
from delta.cli.commands.cmd_quant import CommandQuant
from delta.cli.commands.cmd_portfolio import CommandPortfolio
from delta.cli.commands.cmd_auto import CommandAuto
from delta.cli.commands.cmd_kill import CommandKill

__all__ = [
    "CommandHelp",
    "CommandModel", 
    "CommandAuth",
    "CommandBroker",
    "CommandNews",
    "CommandMacro",
    "CommandTrack",
    "CommandQuant",
    "CommandPortfolio",
    "CommandAuto",
    "CommandKill"
]
