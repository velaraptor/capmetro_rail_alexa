# -*- coding: utf-8 -*-
import logging

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.api_client import DefaultApiClient
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from metro_api.directions_api import get_train
from metro_api import commands
from ask_sdk_model import Response
from ask_sdk_model.slu.entityresolution import StatusCode
from ask_sdk_model.ui import SimpleCard, AskForPermissionsConsentCard
from ask_sdk_model.services.reminder_management import Trigger, TriggerType, AlertInfo, SpokenInfo, SpokenText, \
    PushNotification, PushNotificationStatus, ReminderRequest
from ask_sdk_model.services import ServiceException
import pytz
from datetime import datetime

sb = CustomSkillBuilder(api_client=DefaultApiClient())  # required to use remiders

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
REQUIRED_PERMISSIONS = ["alexa::alerts:reminders:skill:readwrite", "read::alexa:device:all:address"]


# Request Handler classes
class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for skill launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In LaunchRequestHandler")
        speech = commands.WELCOME
        handler_input.response_builder.speak(speech)
        handler_input.response_builder.ask((
            commands.GENERIC_REPROMPT))
        return handler_input.response_builder.response


class NextTrainIntentHandler(AbstractRequestHandler):
    """Handler for times intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("TimesIntent")(handler_input)

    @staticmethod
    def get_address(handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory

        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(commands.NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=REQUIRED_PERMISSIONS))
            return response_builder.response

        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)

            if addr.address_line1 is None and addr.state_or_region is None:
                response_builder.speak(commands.NO_ADDRESS)
            else:
                return addr.address_line1 + ' ' + addr.state_or_region + ' ' +addr.postal_code
        except ServiceException:
            response_builder.speak(commands.ERROR)
            return response_builder.response
        except Exception as e:
            raise e

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In NextTrainIntentHandler")

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        address_response = self.get_address(handler_input)
        if type(address_response) != str:
            return address_response

        try:
            dep_station = handler_input.request_envelope.request.intent.slots['dep_station']
            status = dep_station.resolutions.resolutions_per_authority[0].status.code
            id_key = 'CRE'
            if status == StatusCode.ER_SUCCESS_MATCH:
                id_key = dep_station.resolutions.resolutions_per_authority[0].values[0].value.id
            departing_station = commands.METRO_STATIONS[id_key]
        except Exception as e:
            logger.debug(str(e))
            departing_station = 'Crestview Station'

        try:
            arr_station = handler_input.request_envelope.request.intent.slots['arr_station']
            status_arr = arr_station.resolutions.resolutions_per_authority[0].status.code
            id_key_arr = 'DWT'
            if status_arr == StatusCode.ER_SUCCESS_MATCH:
                id_key_arr = arr_station.resolutions.resolutions_per_authority[0].values[0].value.id
            arrival_station = commands.METRO_STATIONS[id_key_arr]
        except Exception as e:
            logger.debug(str(e))
            arrival_station = 'Austin Convention Center'

        logger.info('Address {}'.format(address_response))
        response, second_train, tz_dict = get_train(home_address=address_response, departing_station=departing_station,
                                                    location=arrival_station)
        check = all(response[value] is None for value in response if value in ['arrival_time_epoch',
                                                                               'departure_time_epoch',
                                                                               'arrival_time_local',
                                                                               'departure_time_local',
                                                                               'day_indicator'])
        set_reminder = True
        if not check:
            speech = ("The next {line} coming to {departing_station} will leave at "
                      "{departure_time_local} {day_indicator} and arrive at the {arrival_station}"
                      " at {arrival_time_local}.").format(**response)

            time_to_get_there = ' You should leave your apartment by ' + tz_dict['relative'] + \
                                ' to make it to the train.'
            speech = speech + time_to_get_there
        else:
            speech = 'Could not find times for that station.'
            set_reminder = False

        check_2 = True
        logger.info(second_train)
        if second_train:
            check_2 = all(response[value] is None for value in second_train if value in
                          ['arrival_time_epoch', 'departure_time_epoch', 'arrival_time_local',
                           'departure_time_local', 'day_indicator'])
        if not check_2:
            second_train_speech = ' After this the next {line} will leave at {departure_time_local}'.format(
                **second_train)
        else:
            second_train_speech = ''
        speech = speech + second_train_speech
        speech = speech + '. Do you want to set a reminder?' if set_reminder else speech
        logger.info(speech)
        ask_question = 'Do you want to set a reminder?' if set_reminder else 'Anything else I can do?'
        session_attr['station'] = response['line']
        session_attr['walking_time'] = tz_dict['epoch']
        handler_input.response_builder.speak(speech).ask(ask_question)
        return handler_input.response_builder.response


class YesMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for yes to get more info intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AMAZON.YesIntent")(handler_input) and
                "station" in session_attr)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        rb = handler_input.response_builder
        request_envelope = handler_input.request_envelope
        permissions = request_envelope.context.system.user.permissions
        reminder_service = handler_input.service_client_factory.get_reminder_management_service()

        if not (permissions and permissions.consent_token):
            logging.info("user hasn't granted reminder permissions")
            return rb.speak("Please give permissions to set reminders using the alexa app.") \
                .set_card(AskForPermissionsConsentCard(permissions=REQUIRED_PERMISSIONS)) \
                .response

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes

        tz = pytz.timezone('America/Chicago')
        nt = datetime.fromtimestamp(session_attr['walking_time']).astimezone(tz)
        notification_time = nt.strftime("%Y-%m-%dT%H:%M:%S")
        logger.info("Notification Time {}".format(notification_time))

        trigger = Trigger(TriggerType.SCHEDULED_ABSOLUTE, notification_time, time_zone_id=commands.TIME_ZONE_ID)
        text = SpokenText(locale='en-US', ssml='<speak>This is your reminder to leave to get the next train</speak>',
            text='This is your reminder to leave to get the next train')
        alert_info = AlertInfo(SpokenInfo([text]))
        push_notification = PushNotification(PushNotificationStatus.ENABLED)
        reminder_request = ReminderRequest(notification_time, trigger, alert_info, push_notification)
        logger.info(reminder_request)
        try:
            reminder_response = reminder_service.create_reminder(reminder_request)
        except ServiceException as e:
            # see: https://developer.amazon.com/docs/smapi/alexa-reminders-api-reference.html#error-messages
            logger.error(e)
            raise e

        return rb.speak("reminder created") \
            .set_card(SimpleCard("Notify Me", "leave to get the next train")) \
            .set_should_end_session(True) \
            .response


class NoMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for no to get no more info intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AMAZON.NoIntent")(handler_input) and
                "station" in session_attr)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In NoMoreInfoIntentHandler")

        speech = "Ok. Safe Travels!"
        handler_input.response_builder.speak(speech).set_should_end_session(True)
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

        handler_input.response_builder.speak((
            commands.HELP)).ask(commands.HELP)
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

        handler_input.response_builder.speak((
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
sb.add_request_handler(YesMoreInfoIntentHandler())
sb.add_request_handler(NoMoreInfoIntentHandler())
sb.add_request_handler(NextTrainIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(ExitIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

# Add exception handler to the skill.
sb.add_exception_handler(CatchAllExceptionHandler())

# Expose the lambda handler to register in AWS Lambda.
lambda_handler = sb.lambda_handler()
