import I2C_LCD_driver
import RPi.GPIO as GPIO
from time import sleep
import adafruit_fingerprint
import serial
import requests
import datetime
import threading

# Initialize serial connection for Adafruit Fingerprint Sensor
try:
    uart = serial.Serial('/dev/ttyUSB0', baudrate=57600, timeout=1)
    fingerprint_sensor = adafruit_fingerprint.Adafruit_Fingerprint(uart)
    if fingerprint_sensor is None:
        raise ValueError('Failed to initialize fingerprint sensor!')
    print('Fingerprint sensor initialized successfully.')
except Exception as e:
    print('Failed to initialize fingerprint sensor:', e)
    exit(1)

# Initialize LCD
lcd = I2C_LCD_driver.lcd()

# Setup GPIO pins
C1, C2, C3, C4 = 5, 6, 13, 19
R1, R2, R3, R4 = 12, 16, 20, 21
buzzer, Relay = 17, 27

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(buzzer, GPIO.OUT)
GPIO.setup(Relay, GPIO.OUT)
GPIO.output(Relay, GPIO.HIGH)

GPIO.setup(C1, GPIO.OUT)
GPIO.setup(C2, GPIO.OUT)
GPIO.setup(C3, GPIO.OUT)
GPIO.setup(C4, GPIO.OUT)

GPIO.setup(R1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(R2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(R3, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(R4, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

keypadPressed = -1
input_pin = ""
failed_attempts = 0
consecutive_wrong_attempts = 0  # Initialize counter for wrong attempts
alarm_triggered = False
manual_control = False  # New flag to track manual control state

def fetch_temperature():
    """Fetch the latest temperature data from the API and trigger alarm if temperature is >= 40°C."""
    api_url_temp = 'https://lockup.pro/api/temperatures'
    try:
        response = requests.get(api_url_temp)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print("No temperature data received.")
            return None, None
        
        latest_record = data[-1]  # Get the last record in the list (most recent)
        temperature = float(latest_record.get('temperature'))
        humidity = float(latest_record.get('humidity'))
        print(f"Fetched temperature: {temperature}°C, Humidity: {humidity}%")
        
        if temperature >= 40:
            print("Temperature is >= 40°C. Triggering buzzer alarm!")
            trigger_alarm()
        
        return temperature, humidity
    except Exception as e:
        print('Failed to fetch temperature data:', e)
        return None, None

    
def fetch_api_data(pin_input):
    """Fetch instructor data from API using the provided PIN."""
    api_url_instructor = f'https://lockup.pro/api/instructors/{pin_input}'
    try:
        response = requests.get(api_url_instructor)
        response.raise_for_status()
        data = response.json()
        print('Fetched data from API:', data)  # Print the API response data
        return data  # Return the entire response data
    except Exception as e:
        print('Failed to fetch API data:', e)
        return []

def get_fingerprint():
    """Get a fingerprint image, template it, and see if it matches!
    Returns the matched ID if successful, otherwise None."""
    print("Waiting for image...")
    while fingerprint_sensor.get_image() != adafruit_fingerprint.OK:
        sleep(0.1)
    print("Image detected. Waiting for stable scan...")
    sleep(2)  # Give some time for the user to adjust their finger if needed
    print("Templating...")
    if fingerprint_sensor.image_2_tz(1) != adafruit_fingerprint.OK:
        return None
    print("Searching...")
    result = fingerprint_sensor.finger_fast_search()
    if result == adafruit_fingerprint.OK:
        matched_id = fingerprint_sensor.finger_id
        print(f"Found fingerprint with ID {matched_id}!")
        return matched_id
    else:
        print("No match found or other error")
        return None
def verify_fingerprint_and_pin(pin_input):
    global manual_control, failed_attempts, alarm_triggered, consecutive_wrong_attempts

    try:
        # Fetch instructor data from the API
        instructors = fetch_api_data(pin_input)
        if not instructors:
            lcd.lcd_clear()
            lcd.lcd_display_string("PIN not found", 1, 0)
            sleep(2)
            print('PIN not found')

            consecutive_wrong_attempts += 1
            if consecutive_wrong_attempts >= 3:
                print("3 consecutive wrong PIN attempts. Triggering alarm!")
                lcd.lcd_clear()
                lcd.lcd_display_string("3 Incorrect PINs", 1, 0)
                lcd.lcd_display_string("Alarm Triggered", 2, 0)
                trigger_alarm()
                consecutive_wrong_attempts = 0

            return False

        consecutive_wrong_attempts = 0
        server_time = fetch_server_time()  # Fetch server time
        if server_time is None:
            lcd.lcd_clear()
            lcd.lcd_display_string("Server Time Error", 1, 0)
            sleep(2)
            return False

        current_day = datetime.datetime.now().strftime('%A')
        current_time = datetime.datetime.now().strftime('%H:%M:%S')

        access_granted = False
        for instructor in instructors:
            subject_day = instructor.get('day')
            subject_start_time = instructor.get('start_time')
            subject_end_time = instructor.get('end_time')

            if (subject_day == current_day and
                    subject_start_time <= server_time <= subject_end_time):
                access_granted = True
                username = instructor.get('username', 'Unknown User')
                name = instructor.get('name', 'Unknown Name')

                # Calculate the time 10 minutes before end time
                end_time_dt = datetime.datetime.strptime(subject_end_time, '%H:%M:%S')
                pre_end_time_dt = end_time_dt - datetime.timedelta(minutes=10)
                pre_end_time = pre_end_time_dt.strftime('%H:%M:%S')

                break

        if not access_granted:
            lcd.lcd_clear()
            lcd.lcd_display_string("No Schedule", 1, 0)
            sleep(2)
            print("No valid schedule for this PIN")
            return False

        lcd.lcd_clear()
        lcd.lcd_display_string("Place Finger", 1, 0)
        sleep(1)

        while fingerprint_sensor.get_image() != adafruit_fingerprint.OK:
            sleep(0.1)

        sleep(2)
        
        matched_finger_id = get_fingerprint()
        if matched_finger_id is None:
            print("Fingerprint verification failed")
            lcd.lcd_clear()
            lcd.lcd_display_string("Scan Failed", 1, 0)
            sleep(2)
            return False

        for instructor in instructors:
            stored_finger_id = instructor.get('finger_id')
            print("Stored Finger ID:", stored_finger_id)
            if stored_finger_id is None:
                continue

            if matched_finger_id == stored_finger_id:
                lcd.lcd_clear()
                lcd.lcd_display_string(f"Welcome {name}", 1, 0)
                lcd.lcd_display_string(f"User: {username}", 2, 0)
                GPIO.output(buzzer, GPIO.HIGH)
                sleep(0.3)
                GPIO.output(buzzer, GPIO.LOW)
                GPIO.output(Relay, GPIO.LOW)  # Unlock the system
                unlock_start_time = datetime.datetime.now()
                manual_control = True

                while True:
                    current_time = datetime.datetime.now().strftime('%H:%M:%S')
                    if current_time > subject_end_time:
                        print("End time reached. Locking system.")
                        lcd.lcd_clear()
                        lcd.lcd_display_string("System Locked", 1, 0)
                        GPIO.output(Relay, GPIO.HIGH)  # Lock the system
                        manual_control = False
                        return False

                    if server_time >= pre_end_time and not alarm_triggered:
                        print("10 minutes to end time. Triggering alarm!")
                        lcd.lcd_clear()
                        lcd.lcd_display_string("10 min Warning", 1, 0)
                        trigger_alarm()
                        alarm_triggered = True
                        sleep(5)

                    sleep(1)

        lcd.lcd_clear()
        lcd.lcd_display_string("Access Denied", 1, 0)
        sleep(2)
        return False

    except Exception as e:
        print('Error:', e)
        return False
def fetch_admin_data(pin_input):
    
    """Fetch admin data from API using the provided PIN."""
    api_url_admin = f'https://lockup.pro/api/admin/pin/{pin_input}'
    try:
        response = requests.get(api_url_admin)
        response.raise_for_status()
        data = response.json()
        print('Fetched admin data from API:', data)  # Print the API response data
        return data  # Return the entire response data
    except Exception as e:
        print('Failed to fetch admin API data:', e)
        return []
def verify_admin_fingerprint_and_pin(pin_input):
    global manual_control, input_pin, consecutive_wrong_attempts
    """Verify admin PIN and fingerprint."""
    try:
        # Fetch admin data from the API
        admin = fetch_admin_data(pin_input)
        if not admin:
            lcd.lcd_clear()
            lcd.lcd_display_string("Admin PIN ", 1, 0)
            lcd.lcd_display_string(" Not found", 2, 0)
            sleep(2)
            consecutive_wrong_attempts += 1
            if consecutive_wrong_attempts >= 3:
                trigger_alarm()  # Trigger the alarm for 10 seconds
                consecutive_wrong_attempts = 0  # Reset the counter after alarming
            return False

        lcd.lcd_clear()
        lcd.lcd_display_string("Admin Place ", 1, 0)
        lcd.lcd_display_string(" Finger", 2, 0)
        sleep(1)

        while fingerprint_sensor.get_image() != adafruit_fingerprint.OK:
            sleep(0.1)

        sleep(2)
        
        matched_finger_id = get_fingerprint()
        if matched_finger_id is None:
            print("Fingerprint verification failed")
            lcd.lcd_clear()
            lcd.lcd_display_string("Scan Failed", 1, 0)
            sleep(2)
            consecutive_wrong_attempts += 1
            if consecutive_wrong_attempts >= 3:
                trigger_alarm()  # Trigger the alarm for 10 seconds
                consecutive_wrong_attempts = 0  # Reset the counter after alarming
            return False

        stored_finger_id = admin.get('finger_id')
        print("Stored Admin Finger ID:", stored_finger_id)
        if stored_finger_id is None or matched_finger_id != stored_finger_id:
            lcd.lcd_clear()
            lcd.lcd_display_string("Admin Access Denied", 1, 0)
            sleep(2)
            consecutive_wrong_attempts += 1
            if consecutive_wrong_attempts >= 3:
                trigger_alarm()  # Trigger the alarm for 10 seconds
                consecutive_wrong_attempts = 0  # Reset the counter after alarming
            manual_control = False
            return False

        # If access is granted, reset the consecutive_wrong_attempts counter
        consecutive_wrong_attempts = 0
        
        lcd.lcd_clear()
        lcd.lcd_display_string(f"Admin Access", 1, 0)
        GPIO.output(buzzer, GPIO.HIGH)
        sleep(0.3)
        GPIO.output(buzzer, GPIO.LOW)
        GPIO.output(Relay, GPIO.LOW)  # Unlock the system
        manual_control = True
        print("Admin Access Granted. System Unlocked.")
        
        # Here, admin can lock/unlock the system manually
        while True:
            lcd.lcd_display_string("Press * to Lock", 2, 0)
            input_pin = ""  # Clear input_pin to ensure fresh input for "*"
            
            while len(input_pin) < 1:  # Wait for the admin to press a key
                setAllColumns(GPIO.LOW)
                readLine(C1, ["D", "C", "B", "A"])
                readLine(C2, ["#", "9", "6", "3"])
                readLine(C3, ["0", "8", "5", "2"])
                readLine(C4, ["*", "7", "4", "1"])
                sleep(0.1)

            if input_pin == "*":  # If the admin presses the * button
                GPIO.output(Relay, GPIO.HIGH)  # Lock the system
                lcd.lcd_clear()
                lcd.lcd_display_string("System Locked", 1, 0)
                print("System Locked by Admin.")
                sleep(2)
                manual_control = False
                break

        return True

    except Exception as e:
        print('Error:', e)
        return False

def fetch_server_time():
    """Fetch the current server time from the API."""
    api_url_time = 'https://lockup.pro/api/time/24-hour'  # Replace with your actual API endpoint for server time
    try:
        response = requests.get(api_url_time)
        response.raise_for_status()
        data = response.json()
        server_time = data.get('time')  # Ensure your API returns time in 'HH:MM:SS' format
        print('Fetched server time from API:', server_time)
        return server_time
    except Exception as e:
        print('Failed to fetch server time:', e)
        return None
    sleep(0.1)

def check_lock_status():
    """Fetch lock status from the API and control the relay accordingly."""
    api_url_lock_status = 'https://lockup.pro/api/logs'
    global manual_control  # Use the manual control flag to avoid conflict

    while True:
        if not manual_control:  # Only check API if not under manual control
            try:
                response = requests.get(api_url_lock_status)
                response.raise_for_status()
                data = response.json()
                status = data.get('status')
                
                if status == 'unlock':
                    print('Unlocking system via API')
                    GPIO.output(Relay, GPIO.LOW)  # Unlock the system
                elif status == 'lock':
                    print('Locking system via API')
                    GPIO.output(Relay, GPIO.HIGH)  # Lock the system

            except Exception as e:
                print('Failed to fetch lock status:', e)

        sleep(5)  # Check every 10 seconds


def trigger_alarm(duration=10, interval=0.1):
    """Trigger the buzzer for the specified duration with the given interval."""
    for _ in range(int(duration / interval)):
        GPIO.output(buzzer, GPIO.HIGH)
        sleep(interval)
        GPIO.output(buzzer, GPIO.LOW)
        sleep(interval)

def setAllColumns(state):
    GPIO.output(C1, state)
    GPIO.output(C2, state)
    GPIO.output(C3, state)
    GPIO.output(C4, state)

def readLine(line, characters):
    global input_pin, manual_control
    GPIO.output(line, GPIO.HIGH)
    if GPIO.input(R1) == 1:
        keypadPressed = characters[0]
        print(keypadPressed)
        if keypadPressed == "D":
            input_pin = ""  # Clear the input PIN
            lcd.lcd_display_string("PIN Cleared   ", 2, 0)  # Update LCD
            sleep(1)  # Briefly show the cleared message
            lcd.lcd_display_string("PIN:          ", 2, 0)  # Reset LCD to show empty PIN
        else:
            input_pin += keypadPressed
    if GPIO.input(R2) == 1:
        keypadPressed = characters[1]
        print(keypadPressed)
        input_pin += keypadPressed
    if GPIO.input(R3) == 1:
        keypadPressed = characters[2]
        print(keypadPressed)
        input_pin += keypadPressed
    if GPIO.input(R4) == 1:
        keypadPressed = characters[3]
        print(keypadPressed)
        input_pin += keypadPressed
    GPIO.output(line, GPIO.LOW)


# Start the lock status check in a separate thread
lock_status_thread = threading.Thread(target=check_lock_status)
lock_status_thread.start()


# Main loop
print("Starting main loop")
try:
    while True:
        temperature, humidity = fetch_temperature()
        
        lcd.lcd_display_string("Enter Your PIN:", 1, 0)

        setAllColumns(GPIO.LOW)
        readLine(C1, ["D", "C", "B", "A"])  # Assign D button for clearing input
        readLine(C2, ["#", "9", "6", "3"])
        readLine(C3, ["0", "8", "5", "2"])
        readLine(C4, ["*", "7", "4", "1"])
        sleep(0.1)

        # Update the LCD with the input PIN
        lcd.lcd_display_string(f"PIN: {input_pin}", 2, 0)

        # Limit input PIN to 4 digits
        if len(input_pin) >= 4:
            print("Input PIN:", input_pin)

            # First check if the PIN belongs to an admin
            if verify_admin_fingerprint_and_pin(input_pin):
                print("Admin Access granted.")
            else:
                # If not an admin, proceed with regular verification
                if verify_fingerprint_and_pin(input_pin):
                    print("Access granted.")
                else:
                    print("Access denied.")

            input_pin = ""  # Reset input PIN after checking
            lcd.lcd_clear()  # Clear LCD after checking
            sleep(1)

except KeyboardInterrupt:
    print("Terminated by user")
finally:
    GPIO.cleanup()
    print("Cleaned up GPIO pins")