# -*- coding: utf-8 -*-

# This is a simple Hello World Alexa Skill, built using
# the implementation of handler classes approach in skill builder.
import logging

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from metro_api.directions_api import main
from metro_api import commands
from ask_sdk_model import Response

sb = SkillBuilder()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Request Handler classes
class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for skill launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In LaunchRequestHandler")
        _ = handler_input.attributes_manager.request_attributes["_"]

        # logger.info(_("This is an untranslated message"))

        speech = _(commands.WELCOME)
        speech += " " + _(commands.HELP)
        handler_input.response_builder.speak(speech)
        handler_input.response_builder.ask(_(
            commands.GENERIC_REPROMPT))
        return handler_input.response_builder.response


class AboutIntentHandler(AbstractRequestHandler):
    """Handler for about intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AboutIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In AboutIntentHandler")
        _ = handler_input.attributes_manager.request_attributes["_"]

        handler_input.response_builder.speak(_(commands.ABOUT))
        return handler_input.response_builder.response


class NextTrainIntentHandler(AbstractRequestHandler):
    """Handler for times intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("TimesIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In NextTrainIntentHandler")

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes

        response = main(location='Crestview Station')
        check = all(response[value] is None for value in response if value in ['arrival_time_epoch',
                                                                               'departure_time_epoch', 'line',
                                                                               'arrival_time_local',
                                                                               'departure_time_local',
                                                                               'day_indicator'])
        if not check:
            speech = ("The next {line} coming to {departing_station} will leave at "
                      "{departure_time_local} {day_indicator} and arrive at the {arrival_station}"
                      " at {arrival_time_local}").format(**response)
        else:
            speech = {'Could not find times for that station.'}
        session_attr['station'] = response['line']

        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for skill session end."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In SessionEndedRequestHandler")
        logger.info("Session ended with reason: {}".format(
            handler_input.request_envelope.request.reason))
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for help intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In HelpIntentHandler")
        _ = handler_input.attributes_manager.request_attributes["_"]

        handler_input.response_builder.speak(_(
            commands.HELP)).ask(_(commands.HELP))
        return handler_input.response_builder.response


class ExitIntentHandler(AbstractRequestHandler):
    """Single Handler for Cancel, Stop intents."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In ExitIntentHandler")
        _ = handler_input.attributes_manager.request_attributes["_"]

        handler_input.response_builder.speak(_(
            commands.STOP)).set_should_end_session(True)
        return handler_input.response_builder.response


# Exception Handler classes
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Catch All Exception handler.
    This handler catches all kinds of exceptions and prints
    the stack trace on AWS Cloudwatch with the request envelope."""
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)
        logger.info("Original request was {}".format(
            handler_input.request_envelope.request))

        speech = "Sorry, there was some problem. Please try again!!"
        handler_input.response_builder.speak(speech).ask(speech)

        return handler_input.response_builder.response


# Add all request handlers to the skill.
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(NextTrainIntentHandler())
sb.add_request_handler(AboutIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(ExitIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

# Add exception handler to the skill.
sb.add_exception_handler(CatchAllExceptionHandler())

# Expose the lambda handler to register in AWS Lambda.
lambda_handler = sb.lambda_handler()