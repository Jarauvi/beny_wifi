import logging  # noqa: D100

from .const import (  # noqa: D100
    CHARGER_COMMAND,
    CHARGER_STATE,
    CLIENT_MESSAGE,
    COMMON,
    REQUEST_TYPE,
    SERVER_MESSAGE,
    TIMER_STATE,
    calculate_checksum,
    validate_checksum,
)
from .conversions import (  # type: ignore  # noqa: PGH003
    convert_weekdays_to_dict,
    get_ip,
    get_message_type,
    get_model,
)

_LOGGER = logging.getLogger(__name__)

def read_message(data, msg_type:str | None = None) -> dict:  # noqa: C901
    """Convert ascii hex string to dict.

    Args:
        data (str): beny client or server message as ascii hex string
        msg_type (str): if message type is not autodetected

    Returns:
        dict: dict containing translated parameters from message

    """

    # check if checksum matches before trying to translate
    if not validate_checksum(data):
        return None

    if not msg_type:
        # try to find out message type automatically
        msg_type = get_message_type(data)

    msg = {"message_type": str(msg_type)}

    # common message header parameters first
    for param, pos in COMMON.FIXED_PART.value["structure"].items():
        msg[param] = int(data[pos], 16)

    # server sends 1-phase or 3-phase values like voltages, currents etc.
    if msg_type in (SERVER_MESSAGE.SEND_VALUES_1P, SERVER_MESSAGE.SEND_VALUES_3P):
        for param, pos in msg_type.value["structure"].items():
            value = int(data[pos], 16)
            try:
                if param == "state":
                    msg[param] = CHARGER_STATE(value).name
                elif param == "timer_state":
                    msg[param] = TIMER_STATE(value).name
                elif param == "total_kwh":
                    msg[param] = float(value) / 10
                elif param == "request_type":
                    msg[param] = REQUEST_TYPE(value).name
                else:
                    msg[param] = value
            except ValueError:
                _LOGGER.error(f"Invalid value for {param}: value")  # noqa: G004
                msg[param] = None

    if msg_type == SERVER_MESSAGE.SEND_DLB:
        for param, pos in msg_type.value["structure"].items():
            value = int(data[pos], 16)
            try:
                if param == "grid_power":
                    # Grid power can be negative (exporting) - handle as signed 16-bit integer
                    # Check if the high bit is set (value >= 0x8000 for 16-bit)
                    if value >= 0x8000:
                        # Convert from two's complement
                        value = value - 0x10000
                    msg[param] = float(value) / 10
                elif param in ["ev_power", "house_power", "solar_power"]:
                    msg[param] = float(value) / 10
                else:
                    msg[param] = value
            except ValueError:
                _LOGGER.error(f"Invalid value for {param}: value")  # noqa: G004
                msg[param] = None

    # server sends charger model
    if msg_type == SERVER_MESSAGE.SEND_MODEL:
        for param, pos in msg_type.value["structure"].items():
            if param == "model":
                msg["model"] = get_model(data)
            elif param == "request_type":
                msg[param] = REQUEST_TYPE(int(data[pos], 16)).name

    # handshake - server sends serial, ip and port
    elif msg_type == SERVER_MESSAGE.HANDSHAKE:
        msg["serial"] = int(data[SERVER_MESSAGE.HANDSHAKE.value["structure"]["serial"]], 16)
        msg["ip"] = get_ip(data)
        msg["port"] = int(data[SERVER_MESSAGE.HANDSHAKE.value["structure"]["port"]], 16)

    # server sends settings
    if msg_type == SERVER_MESSAGE.SEND_SETTINGS:
        for param, pos in msg_type.value["structure"].items():
            value = int(data[pos], 16)
            if param == "weekdays":
                if value == 0:
                    msg["schedule"] = "disabled"
                else:
                    msg["schedule"] = "enabled"

                msg[param] = convert_weekdays_to_dict(value)
            else:
                msg[param] = value

    # client sends command to start or stop the charging
    elif msg_type == CLIENT_MESSAGE.SEND_CHARGER_COMMAND:
        for param, pos in msg_type.value["structure"].items():
            msg[param] =  CHARGER_COMMAND(int(data[pos], 16)).name

    # client sends data request
    # ("values" or "model" are known at the moment)
    elif msg_type == CLIENT_MESSAGE.REQUEST_DATA:
        for param, pos in msg_type.value["structure"].items():
            msg[param] = REQUEST_TYPE(int(data[pos], 16)).name

    elif msg_type == CLIENT_MESSAGE.SET_TIMER:
        for param, pos in msg_type.value["structure"].items():
            msg[param] = int(data[pos], 16)

    _LOGGER.debug(f"Message received: {data}={msg}")  # noqa: G004

    return msg

def build_message(message: SERVER_MESSAGE | CLIENT_MESSAGE, params: dict = {}) -> str:
    """Build command message that can be sent to charger.

    Args:
        message (SERVER_MESSAGE | CLIENT_MESSAGE): message type to be built
        params (dict, optional): parameters as dict to be appended to message {"parameter": "value"}

    Returns:
        str: ascii hex string

    """

    msg = message.value["hex"]
    for param, val in params.items():
        if param in msg:
            msg = msg.replace("[" + param + "]", val)

    checksum = calculate_checksum(msg)

    msg = msg.replace("[checksum]", f"{checksum:02x}")
    _LOGGER.debug(f"Message sent. Type: {message.name}. Content: {msg!s}={params}")  # noqa: G004

    return msg