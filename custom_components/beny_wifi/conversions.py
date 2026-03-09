from .const import CLIENT_MESSAGE, COMMON, SERVER_MESSAGE  # noqa: D100


def get_hex(data: int, length: int = 2) -> str:
    """Convert int to hex string.

    Args:
        data (int): integer value converted
        length (int): padding size

    Returns:
        str: hex string

    """
    return f"{data:0{length}x}"

def convert_timer(start_time_str: str, end_time_str: str) -> dict:
    """Convert start and end times to timer parameters.

    Args:
        start_time_str (str): charging start time "08:00"
        end_time_str (str): charging end time "10:30"

    Returns:
        dict: timer values

    """
    times = {}
    time_params = start_time_str.split(':')
    times["start_h"] = get_hex(int(time_params[0]))
    times["start_min"] = get_hex(int(time_params[1]))
    # set end time
    if end_time_str:
        times["end_timer_set"] = "11111"
        time_params = end_time_str.split(':')
        times["end_h"] = get_hex(int(time_params[0]))
        times["end_min"] = get_hex(int(time_params[1]))
    # no end time given
    else:
        times["end_timer_set"] = "00000"
        times["end_h"] = get_hex(0)
        times["end_min"] = get_hex(0)

    return times

def convert_schedule(weekdays: list[bool], start_time_str: str, end_time_str: str):
    """Convert schedule data to hex.

    Args:
        weekdays (list[bool]): list of booleans for weekdays
        start_time_str (str): charging start time
        end_time_str (str): charging end time

    Returns:
        dict: dict of hex values

    """
    params = {}
    params["weekdays"] = convert_weekdays_to_hex(weekdays)
    time_params = start_time_str.split(':')
    params["start_h"] = get_hex(int(time_params[0]))
    params["start_min"] = get_hex(int(time_params[1]))
    time_params = end_time_str.split(':')
    params["end_h"] = get_hex(int(time_params[0]))
    params["end_min"] = get_hex(int(time_params[1]))

    return params

def convert_weekdays_to_dict(weekdays: int):
    """Convert an integer value to a dictionary mapping weekdays to boolean states.

    Args:
        weekdays (int): An integer representing the weekday bits (e.g., 0x0d or 127).

    Returns:
        dict: A dictionary with weekdays as keys and bit states as booleans.

    """

    # Convert the integer to a 7-bit binary string
    binary_value = bin(weekdays)[2:].zfill(7)  # Ensure 7 bits for weekdays

    # Map weekdays to the corresponding binary bits
    weekdays = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

    # Create the dictionary mapping weekdays to boolean values
    return {day: bool(int(bit)) for day, bit in zip(weekdays, reversed(binary_value), strict=False)}

def convert_weekdays_to_hex(weekdays: list[bool]):
    """Convert list of booleans to hex.

    Args:
        weekdays (list[bool]): list of booleans for weekday states

    Returns:
        str: hex of weekday states

    """

    bin_val = ''.join(['1' if day else '0' for day in weekdays])
    return f"{int(bin_val, 2):02x}"

def convert_serial_to_hex(serial_number: int) -> str:
    """Convert serial number to hex.

    Args:
        serial_number (int): 9 digit serial number

    Returns:
        str: serial number as hex

    """

    return f"{int(serial_number):08X}".lower()

def convert_pin_to_hex(pin: int) -> str:
    """Convert pin to hex.

    Args:
        pin (int): 6 digit pin

    Returns:
        str: pin as hex

    """

    return f"{int(pin):05X}".lower()

def get_message_type(data: str) -> CLIENT_MESSAGE | SERVER_MESSAGE:
    """Get message structure by id.

    Args:
        data (str): message as ascii hex string

    Returns:
        _type_: _description_

    """
    message_type = data[COMMON.FIXED_PART.value["structure"]["message_type"]]
    msg_int = int(data[COMMON.FIXED_PART.value["structure"]["message_id"]], 16)

    if msg_int == 11:
        return CLIENT_MESSAGE.REQUEST_DATA
    if msg_int == 28:
        return CLIENT_MESSAGE.SET_TIMER
    if msg_int == 12:
        return CLIENT_MESSAGE.SEND_CHARGER_COMMAND

    if msg_int == 8:
        return SERVER_MESSAGE.ACCESS_DENIED
    if msg_int == 30:
        return SERVER_MESSAGE.SEND_VALUES_1P
    
    # BCP-A2N-L v1.28 firmware changed msg_int to 31, adding support
    if msg_int == 31:
        return SERVER_MESSAGE.SEND_VALUES_1P
        
    # Additional status message type 36 added
    if msg_int == 35 or msg_int == 36:
        return SERVER_MESSAGE.SEND_VALUES_3P
    if msg_int == 33:
        return SERVER_MESSAGE.SEND_DLB
    if msg_int == 17:
        if message_type.upper() == '7B':
            return SERVER_MESSAGE.SEND_DLB

        return SERVER_MESSAGE.HANDSHAKE
    if msg_int == 32:
        return SERVER_MESSAGE.SEND_MODEL

    # DLB config ACK/response: message_type=6b (107), message_id=0x0012 (18)
    if msg_int == 18 and int(data[4:6], 16) == 0x6b:
        return SERVER_MESSAGE.SEND_DLB_CONFIG

    return None

def get_ip(data: str) -> str:
    """Read ip from message.

    Args:
        data (str): message as ascii hex string

    Returns:
        str: ip address

    """

    ip_pos = SERVER_MESSAGE.HANDSHAKE.value["structure"]["ip"]

    # Assuming the IP address starts from index 20 and ends at 28 (adjustable)
    return '.'.join(str(int(data[i:i+2], 16)) for i in range(ip_pos.start, ip_pos.stop, ip_pos.step))

def get_model(data: str) -> str:
    """Read model from message.

    Args:
        data (str): message as ascii hex string

    Returns:
        _type_: _description_

    """

    # Convert hex string to bytes
    data = bytes.fromhex(data)

    # The header length appears to be fixed at 8 bytes (adjust if needed)
    header_length = 8

    # Start searching for the model name after the header
    start_index = None
    for i in range(header_length, len(data)):  # Start after header
        if 32 <= data[i] <= 126:  # Printable ASCII range
            start_index = i
            break

    if start_index is None:
        return "Model name not found"

    # Extract printable characters until a null byte (0x00) or non-ASCII character
    model_bytes = []
    for i in range(start_index, len(data)):
        if i != start_index and data[i] == 0x00:  # Stop at the first null byte
            break
        model_bytes.append(data[i])

    # Return ASCII string
    return bytes(model_bytes).decode('ascii')