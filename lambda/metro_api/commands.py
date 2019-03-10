# Resolving gettext as _ for module loading.
from gettext import gettext as _

SKILL_NAME = "MetroRail Guide"

WELCOME = _("Welcome to MetroRail Guide!")
HELP = _("Give a station you are leaving from and get next departure time and arrival time to downtown.")
ABOUT = _("CapMetro MetroRail is a commuter train in Austin..")
STOP = _("Okay!")
FALLBACK = _("The {} can't help you with that. It can help you get times for the MetroRail. What can I help you with?")
GENERIC_REPROMPT = _("What can I help you with?")
