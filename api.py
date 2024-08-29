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
alarm_triggered = False

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
    global failed_attempts, alarm_triggered
    try:
        # Prompt user to place their finger
        lcd.lcd_clear()
        lcd.lcd_display_string("Place Finger", 1, 0)
        sleep(1)

        # Wait until a finger is detected before scanning
        print("Waiting for finger...")
        while fingerprint_sensor.get_image() != adafruit_fingerprint.OK:
            sleep(0.1)  # Small delay to avoid busy-waiting

        # Give the user some time to adjust their finger if needed
        sleep(2)
        
        # Get and verify fingerprint details
        matched_finger_id = get_fingerprint()
        if matched_finger_id is None:
            print("Fingerprint verification failed")
            lcd.lcd_clear()
            lcd.lcd_display_string("Scan Failed", 1, 0)
            sleep(2)
            return False

        # Fetch instructor data from the API
        instructors = fetch_api_data(pin_input)
        if not instructors:
            lcd.lcd_clear()
            lcd.lcd_display_string("PIN not found", 1, 0)
            sleep(2)
            print('PIN not found')
            return False

        access_granted = False
        current_day = datetime.datetime.now().strftime('%A')
        current_time = datetime.datetime.now().strftime('%H:%M:%S')

        for instructor in instructors:
            stored_finger_id = instructor.get('finger_id')
            print("Stored Finger ID:", stored_finger_id)
            if stored_finger_id is None:
                continue

            if matched_finger_id == stored_finger_id:
                # Check the schedule
                subject_day = instructor.get('day')
                subject_start_time = instructor.get('start_time')
                subject_end_time = instructor.get('end_time')

                if (subject_day == current_day and
                        subject_start_time <= current_time <= subject_end_time):
                    access_granted = True
                    username = instructor.get('username', 'Unknown User')
                    name = instructor.get('name', 'Unknown Name')
                    
                    # Calculate the time 10 minutes before end time
                    end_time_dt = datetime.datetime.strptime(subject_end_time, '%H:%M:%S')
                    pre_end_time_dt = end_time_dt - datetime.timedelta(minutes=10)
                    pre_end_time = pre_end_time_dt.strftime('%H:%M:%S')
                    
                    break

        if access_granted:
            # Unlock the system
            lcd.lcd_clear()
            lcd.lcd_display_string(f"Welcome {name}", 1, 0)
            lcd.lcd_display_string(f"User: {username}", 2, 0)
            GPIO.output(buzzer, GPIO.HIGH)
            sleep(0.3)
            GPIO.output(buzzer, GPIO.LOW)
            GPIO.output(Relay, GPIO.LOW)  # Unlock the system
            unlock_start_time = datetime.datetime.now()

            # Continue to check the current time and lock the system if end time is reached
            while True:
                current_time = datetime.datetime.now().strftime('%H:%M:%S')
                if current_time > subject_end_time:
                    print("End time reached. Locking system.")
                    lcd.lcd_clear()
                    lcd.lcd_display_string("System Locked", 1, 0)
                    GPIO.output(Relay, GPIO.HIGH)  # Lock the system
                    return False

                # Trigger pre-end time alarm
                if current_time >= pre_end_time and not alarm_triggered:
                    print("10 minutes to end time. Triggering alarm!")
                    lcd.lcd_clear()
                    lcd.lcd_display_string("10 min Warning", 1, 0)
                    trigger_alarm()  # Trigger the buzzer for 5 seconds
                    alarm_triggered = True  # Ensure the alarm only triggers once
                    sleep(5)  # Sleep for 5 seconds to let the alarm sound

                sleep(1)  # Check every second

        else:
            lcd.lcd_clear()
            lcd.lcd_display_string("Access Not IN", 1, 0)
            lcd.lcd_display_string("Schedule", 2, 0)
            sleep(4)
            GPIO.output(buzzer, GPIO.HIGH)
            sleep(0.3)
            GPIO.output(buzzer, GPIO.LOW)
            failed_attempts += 1

            if failed_attempts >= 3 and not alarm_triggered:
                alarm_triggered = True
                print("Triggering alarm!")
                trigger_alarm()
                sleep(10)
                alarm_triggered = False

            return False

    except Exception as e:
        print('Error:', e)
        return False

def trigger_alarm():
    """Trigger the buzzer alarm for 10 seconds with 3-second intervals."""
    for _ in range(5):
        GPIO.output(buzzer, GPIO.HIGH)
        sleep(1)  # Buzzer on for 1 second
        GPIO.output(buzzer, GPIO.LOW)
        sleep(1)  # Buzzer off for 1 second

def check_lock_status():
    """Fetch lock status from the API and control the relay accordingly."""
    api_url_lock_status = 'http://192.168.1.16:8000/api/logs'
    while True:
        try:
            response = requests.get(api_url_lock_status)
            response.raise_for_status()
            data = response.json()
            status = data.get('status')
            
            if status == 'unlock':
                GPIO.output(Relay, GPIO.LOW)  # Unlock the system
            elif status == 'lock':
                GPIO.output(Relay, GPIO.HIGH)  # Lock the system
            else:
                print('Unknown status:', status)

        except Exception as e:
            print('Failed to fetch lock status:', e)
        
        sleep(0.1)  # Check every 10 seconds

# Start a separate thread for checking lock status
lock_status_thread = threading.Thread(target=check_lock_status)
lock_status_thread.daemon = True  # Daemonize thread to ensure it exits when the main program exits
lock_status_thread.start()

def commands():
    global input_pin, failed_attempts, alarm_triggered
    pressed = False

    GPIO.output(C1, GPIO.HIGH)

    if GPIO.input(R1) == 1:
        print("Input reset!")
        lcd.lcd_clear()
        lcd.lcd_display_string("Clearing...", 1, 5)
        sleep(1)
        pressed = True

    GPIO.output(C1, GPIO.HIGH)

    if not pressed and GPIO.input(R2) == 1:
        if len(input_pin) == 0:
            lcd.lcd_clear()
            lcd.lcd_display_string("Please Input PIN", 1, 0)
            sleep(1)
        else:
            # Fetch instructor data from API
            instructors = fetch_api_data(input_pin)
            
            if not instructors:
                lcd.lcd_clear()
                lcd.lcd_display_string("PIN not found", 1, 0)
                GPIO.output(buzzer, GPIO.HIGH)
                sleep(0.5)
                GPIO.output(buzzer, GPIO.LOW)
                failed_attempts += 1

                if failed_attempts >= 3 and not alarm_triggered:
                    alarm_triggered = True
                    trigger_alarm()
                    sleep(10)
                    alarm_triggered = False

                pressed = True
            else:
                if verify_fingerprint_and_pin(input_pin):
                    lcd.lcd_clear()
                    lcd.lcd_display_string("Access Granted", 1, 0)
                    GPIO.output(buzzer, GPIO.HIGH)
                    sleep(0.3)
                    GPIO.output(buzzer, GPIO.LOW)
                    failed_attempts = 0
                else:
                    lcd.lcd_clear()
                    lcd.lcd_display_string("Access Denied", 1, 0)
                    GPIO.output(buzzer, GPIO.HIGH)
                    sleep(0.3)
                    GPIO.output(buzzer, GPIO.LOW)
                    failed_attempts += 1

                    if failed_attempts >= 3 and not alarm_triggered:
                        alarm_triggered = True
                        trigger_alarm()
                        sleep(10)
                        alarm_triggered = False

                pressed = True

    GPIO.output(C1, GPIO.LOW)

    if pressed:
        input_pin = ""

    return pressed

def read(column, characters):
    global input_pin

    GPIO.output(column, GPIO.HIGH)
    if GPIO.input(R1) == 1:
        input_pin += characters[0]
        lcd.lcd_display_string(str(input_pin), 2, 0)
    if GPIO.input(R2) == 1:
        input_pin += characters[1]
        lcd.lcd_display_string(str(input_pin), 2, 0)
    if GPIO.input(R3) == 1:
        input_pin += characters[2]
        lcd.lcd_display_string(str(input_pin), 2, 0)
    if GPIO.input(R4) == 1:
        input_pin += characters[3]
        lcd.lcd_display_string(str(input_pin), 2, 0)
    GPIO.output(column, GPIO.LOW)

# Main loop
try:
    while True:
        lcd.lcd_display_string("Enter Your PIN:", 1, 0)

        if keypadPressed != -1:
            setAllRows(GPIO.HIGH)
            if GPIO.input(keypadPressed) == 0:
                keypadPressed = -1
            else:
                sleep(0.1)
        else:
            if not commands():
                read(C1, ["D", "C", "B", "A"])
                read(C2, ["#", "9", "6", "3"])
                read(C3, ["0", "8", "5", "2"])
                read(C4, ["*", "7", "4", "1"])
                sleep(0.1)
            else:
                sleep(0.1)
except KeyboardInterrupt:
    print("Stopped!")
finally:
    GPIO.cleanup()
