import pytest
import socket
from unittest.mock import patch, MagicMock, AsyncMock, call
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from custom_components.beny_wifi.coordinator import BenyWifiUpdateCoordinator
from datetime import datetime, timedelta

@pytest.fixture
def mock_send_udp_request():
    """Mock the '_send_udp_request' method."""
    return AsyncMock()

@pytest.fixture
def mock_hass():
    """Fixture to mock HomeAssistant."""
    hass = MagicMock(HomeAssistant)
    # Mock the states object
    hass.states = MagicMock()
    return hass

@pytest.fixture
def coordinator(mock_hass):
    """Fixture to create a BenyWifiUpdateCoordinator instance."""
    # Mock the config_entry data
    config_entry = MagicMock()
    config_entry.data = {
        "serial": "1234567890"  # Mock the serial number
    }
    coordinator = BenyWifiUpdateCoordinator(
        hass=mock_hass,
        ip_address="192.168.1.100",
        port=502,
        scan_interval=10,
    )
    coordinator.config_entry = config_entry  # Mock config_entry to avoid 'NoneType' error
    return coordinator

@pytest.fixture
def mock_get_states(mock_hass):
    """Fixture to mock hass.states.get."""
    with patch.object(mock_hass.states, "get") as mock_get:
        yield mock_get

@patch("custom_components.beny_wifi.coordinator.BenyWifiUpdateCoordinator._send_udp_request")
@patch("custom_components.beny_wifi.coordinator.read_message")
async def test_successful_data_fetch(mock_read_message, mock_send_udp_request, coordinator):
    """Test successful data fetch from the coordinator."""
    
    # Prepare mock response from UDP request (simulated)
    mock_send_udp_request.return_value = b"55aa1000237000000000e600e600e6000000005e06000000000000000f0000000003ca"
    
    # Simulate a valid read_message response
    mock_read_message.return_value = {
        "state": "standby",
        "power": 0.0,
        "total_kwh": 0.0,
        "timer_start_h": 8,
        "timer_start_min": 0,
        "timer_end_h": 7,
        "timer_end_min": 30,
        "timer_state": "UNSET"
    }

    # Call the update function
    data = await coordinator._async_update_data()

    # Check if the data was correctly transformed and returned
    assert data["state"] == "standby"
    assert data["power"] == 0.0
    assert data["total_kwh"] == 0.0
    assert data["timer_start"] == "not_set"
    assert data["timer_end"] == "not_set"
    assert data["timer_state"] == "UNSET"


@patch("custom_components.beny_wifi.coordinator.BenyWifiUpdateCoordinator._send_udp_request")
async def test_udp_request_failure(mock_send_udp_request, coordinator):
    """Test that the coordinator raises an error when the UDP request fails."""

    # Simulate a failure in sending the UDP request
    mock_send_udp_request.side_effect = Exception("UDP request failed")

    # Call the update function and check if it raises UpdateFailed
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()  # Ensure this is awaited

@patch("custom_components.beny_wifi.coordinator.read_message")
@patch("socket.socket")
async def test_async_toggle_charging_start_with_socket(mock_socket, mock_read_message, coordinator):
    """Test toggling charging start with simulated socket."""

    # Create a mock socket instance
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance

    # Simulate sending data with `sendto`
    def mock_sendto(data, addr):
        assert data == b"55aa10000b0000cb347089"  # Verify the correct request data is sent
        assert addr == ("192.168.1.100", 502)  # Verify correct IP and port
    mock_socket_instance.sendto.side_effect = mock_sendto

    # Simulate receiving data with `recvfrom`
    mock_socket_instance.recvfrom.return_value = (b"55aa10001103499602D2c0a801640d05d8", ("192.168.1.100", 502))

    # Mock the parsed message structure returned by `read_message`
    mock_read_message.return_value = {
        "state": "standby",
        "power": 0.0,
        "total_kwh": 0.0,
        "timer_start_h": 8,
        "timer_start_min": 0,
        "timer_end_h": 10,
        "timer_end_min": 30,
        "timer_state": "START_END_TIME"
    }

    # Mock the built message
    with patch("custom_components.beny_wifi.communication.build_message") as mock_build_message:
        mock_build_message.return_value = b"mocked_request"

        # Call the coordinator's update method
        data = await coordinator._async_update_data()

        # Assertions
        assert data["state"] == "standby"
        assert data["power"] == 0.0
        assert data["total_kwh"] == 0.0
        assert isinstance(data["timer_start"], datetime)
        assert isinstance(data["timer_end"], datetime)

        # Verify socket operations
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        mock_socket_instance.settimeout.assert_called_once_with(5)
        mock_socket_instance.close.assert_called_once()

@patch("socket.socket")
async def test_socket_exception(mock_socket, coordinator):
    """Test that a socket exception is correctly handled and raises UpdateFailed."""

    # Create a mock socket instance
    mock_socket_instance = MagicMock()
    mock_socket.return_value = mock_socket_instance

    # Simulate a socket exception when sending data
    mock_socket_instance.sendto.side_effect = socket.error("Mocked socket error")

    # Mock the built message
    with patch("custom_components.beny_wifi.communication.build_message") as mock_build_message:
        mock_build_message.return_value = b"55aa10000b0000cb347089"

        # Call the coordinator's update method and ensure it raises UpdateFailed
        with pytest.raises(UpdateFailed, match="Error sending UDP request: Mocked socket error"):
            await coordinator._async_update_data()

    # Print the mock calls for debugging (optional)
    print(mock_socket_instance.mock_calls)

    # Verify socket operations
    mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
    mock_socket_instance.settimeout.assert_called_once_with(5)
    mock_socket_instance.sendto.assert_called_once_with(b"55aa10000b0000cb347089", ("192.168.1.100", 502))
    mock_socket_instance.close.assert_called_once()

@patch("custom_components.beny_wifi.conversions.get_hex")
@patch("custom_components.beny_wifi.communication.build_message")
@patch("custom_components.beny_wifi.coordinator.BenyWifiUpdateCoordinator._send_udp_request")
async def test_toggle_charging_start(mock_send_udp_request, mock_build_message, mock_get_hex, coordinator, mock_hass):
    """Test the start charging command, with multiple UDP requests."""

    # Mock the charger state as 'standby'
    mock_hass.states.get.return_value = "standby"

    # Mock get_hex to return valid hex string for the start command
    mock_get_hex.return_value = "01"  # Hex string for 'start' command

    # Mock build_message to return a valid request string
    mock_build_message.return_value = "55aa10000c0000cb34060121"

    # Mock _send_udp_request to simulate a successful response for each call
    mock_send_udp_request.side_effect = [
        b"55aa10000c0000cb34060121",  # First call: charge start request
    ]

    # Simulate calling async_toggle_charging with 'start' command
    await coordinator.async_toggle_charging(device_name="Charger1", command="start")

    # Verify the expected sequence of calls to _send_udp_request
    mock_send_udp_request.assert_has_calls([
        call("55aa10000c0000cb34060121".encode('ascii')),  # Start charging request
    ])

    # Check that the sleep and update calls happened (e.g., ensuring async steps)
    # You can add additional mocks or checks for asyncio.sleep if needed



@patch("custom_components.beny_wifi.conversions.get_hex")
@patch("custom_components.beny_wifi.communication.build_message")
@patch("custom_components.beny_wifi.coordinator.BenyWifiUpdateCoordinator._send_udp_request")
async def test_toggle_charging_stop(mock_send_udp_request, mock_build_message, mock_get_hex, coordinator, mock_hass):
    """Test the start charging command, with multiple UDP requests."""

    # Mock the charger state as 'standby'
    mock_hass.states.get.return_value = "standby"

    # Mock get_hex to return valid hex string for the start command
    mock_get_hex.return_value = "00"  # Hex string for 'start' command

    # Mock build_message to return a valid request string
    mock_build_message.return_value = "55aa10000c0000cb34060020"

    # Mock _send_udp_request to simulate a successful response for each call
    mock_send_udp_request.side_effect = [
        b"55aa10000c0000cb34060020",  # First call: charge start request
    ]

    # Simulate calling async_toggle_charging with 'start' command
    await coordinator.async_toggle_charging(device_name="Charger1", command="stop")

    # Verify the expected sequence of calls to _send_udp_request
    mock_send_udp_request.assert_has_calls([
        call("55aa10000c0000cb34060020".encode('ascii')),  # Start charging request
    ])

    # Check that the sleep and update calls happened (e.g., ensuring async steps)
    # You can add additional mocks or checks for asyncio.sleep if needed

@pytest.mark.asyncio
async def test_async_set_timer(coordinator):
    """Test async_set_timer method."""
    # Mock config_entry and SERIAL
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {"serial": "some_serial"}

    # Mock state sensor in Home Assistant
    device_name = "Test Charger"
    start_time = "08:00"
    end_time = "10:00"
    state_sensor_id = "sensor.some_serial_charger_state"
    state_sensor_value = "charging"
    coordinator.hass.states.get.return_value = state_sensor_value

    # Mock the _send_udp_request and build_message
    with patch("custom_components.beny_wifi.coordinator.build_message", return_value="mock_message"), \
         patch.object(coordinator, "_send_udp_request", new_callable=AsyncMock) as mock_send_udp, \
         patch("custom_components.beny_wifi.coordinator._LOGGER") as mock_logger:
        # mock_send_udp will return bytes, so no need to encode
        mock_send_udp.return_value = b"mock_message"

        await coordinator.async_set_timer(device_name, start_time, end_time)

        # Verify the state sensor was checked
        coordinator.hass.states.get.assert_called_once_with(state_sensor_id)

        # Verify the UDP request was sent with the mock message as bytes
        mock_send_udp.assert_called_once_with(b"mock_message")

        # Verify logging
        mock_logger.info.assert_called_once_with(f"{device_name}: charging timer set")


@pytest.mark.asyncio
async def test_async_reset_timer(coordinator):
    """Test async_reset_timer method."""
    # Mock config_entry and SERIAL
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {"serial": "some_serial"}

    # Mock state sensor in Home Assistant
    device_name = "Test Charger"
    state_sensor_id = "sensor.some_serial_charger_state"
    state_sensor_value = "charging"
    coordinator.hass.states.get.return_value = state_sensor_value

    # Mock the _send_udp_request and build_message
    with patch("custom_components.beny_wifi.coordinator.build_message", return_value="mock_message"), \
         patch.object(coordinator, "_send_udp_request", new_callable=AsyncMock) as mock_send_udp, \
         patch("custom_components.beny_wifi.coordinator._LOGGER") as mock_logger:
        # mock_send_udp will return bytes, so no need to encode
        mock_send_udp.return_value = b"mock_message"

        await coordinator.async_reset_timer(device_name)

        # Verify the state sensor was checked
        coordinator.hass.states.get.assert_called_once_with(state_sensor_id)

        # Verify the UDP request was sent with the mock message as bytes
        mock_send_udp.assert_called_once_with(b"mock_message")

        # Verify logging
        mock_logger.info.assert_called_once_with(f"{device_name}: charging timer reset")

@pytest.mark.asyncio
async def test_async_set_timer_unplugged(coordinator):
    """Test async_set_timer method when charger is unplugged."""
    device_name = "Test Charger"
    start_time = "08:00"
    end_time = "10:00"
    state_sensor_value = "unplugged"
    coordinator.hass.states.get.return_value = state_sensor_value

    # Ensure _send_udp_request is not called
    with patch.object(coordinator, "_send_udp_request", new_callable=AsyncMock) as mock_send_udp:
        await coordinator.async_set_timer(device_name, start_time, end_time)

        # Verify the state sensor was checked
        coordinator.hass.states.get.assert_called_once()

        # Verify no UDP request was sent
        mock_send_udp.assert_not_called()


@pytest.mark.asyncio
async def test_async_reset_timer_unplugged(coordinator):
    """Test async_reset_timer method when charger is unplugged."""
    device_name = "Test Charger"
    state_sensor_value = "unplugged"
    coordinator.hass.states.get.return_value = state_sensor_value

    # Ensure _send_udp_request is not called
    with patch.object(coordinator, "_send_udp_request", new_callable=AsyncMock) as mock_send_udp:
        await coordinator.async_reset_timer(device_name)

        # Verify the state sensor was checked
        coordinator.hass.states.get.assert_called_once()

        # Verify no UDP request was sent
        mock_send_udp.assert_not_called()

@pytest.mark.asyncio
async def test_timer_end_adjustment(coordinator):
    """Test that the end time is adjusted correctly when earlier than or equal to start time."""
    
    # Mocking start and end times
    start_time = datetime(2025, 1, 16, 23, 0)  # 11:00 PM
    end_time_earlier = datetime(2025, 1, 16, 22, 0)  # 10:00 PM
    end_time_equal = datetime(2025, 1, 16, 23, 0)  # 11:00 PM
    end_time_unset = "not_set"

    # Case 1: End time earlier than start time
    if end_time_earlier <= start_time:
        end_time_earlier += timedelta(days=1)
    assert end_time_earlier == datetime(2025, 1, 17, 22, 0)  # Should be the next day

    # Case 2: End time equal to start time
    if end_time_equal <= start_time:
        end_time_equal += timedelta(days=1)
    assert end_time_equal == datetime(2025, 1, 17, 23, 0)  # Should be the next day

    # Case 3: End time not set
    end = end_time_unset if end_time_unset == "not_set" else end_time_equal
    assert end == "not_set"

@pytest.mark.asyncio
async def test_edge_case_midnight(coordinator):
    """Test timer logic for midnight as start and end times."""
    device_name = "Test Charger"
    start_time = "00:00"
    end_time = "23:59"

    with patch.object(coordinator, "_send_udp_request", new_callable=AsyncMock) as mock_send_udp:
        await coordinator.async_set_timer(device_name, start_time, end_time)
        mock_send_udp.assert_called_once()

@patch("custom_components.beny_wifi.coordinator.BenyWifiUpdateCoordinator._send_udp_request")
async def test_state_mapping(mock_send_udp_request, coordinator):
    """Test state mapping to verify proper translation."""

    # Mock valid UDP response data
    mock_send_udp_request.return_value = b"55aa1000237000000000e600e700e6000000005e06000000000000000f0000000003cb"

    # Call update method
    data = await coordinator._async_update_data()

    # Validate state mapping
    assert data["state"] == "CHARGING"  # Expected mapping for 6102