import mysql.connector
import serial
import I2C_LCD_driver
import RPi.GPIO as GPIO
from time import sleep
from pyfingerprint.pyfingerprint import PyFingerprint

# MySQL connection details
db_config = {
    'user': 'root',
    'password': '123456789',
    'host': 'localhost',
    'database': 'testdb'
}

# Initialize MySQL connection
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

# Initialize fingerprint sensor
try:
    fingerprint_sensor = PyFingerprint('/dev/ttyUSB0', 57600)  # Adjust port and baud rate if needed
except Exception as e:
    print('Failed to initialize fingerprint sensor:', e)
    exit(1)

# Initialize LCD
lcd = I2C_LCD_driver.lcd()

# Setup GPIO pins
C1 = 5
C2 = 6
C3 = 13
C4 = 19
R1 = 12
R2 = 16
R3 = 20
R4 = 21
buzzer = 17
Relay = 27

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(buzzer, GPIO.OUT)
GPIO.setup(Relay, GPIO.OUT)
GPIO.output(Relay, GPIO.HIGH)

# Set column pins as output pins
GPIO.setup(C1, GPIO.OUT)
GPIO.setup(C2, GPIO.OUT)
GPIO.setup(C3, GPIO.OUT)
GPIO.setup(C4, GPIO.OUT)

# Set row pins as input pins
GPIO.setup(R1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(R2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(R3, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(R4, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Initialize variables
keypadPressed = -1
input_pin = ""
failed_attempts = 0
alarm_triggered = False

def verify_fingerprint_and_pin(pin_input):
    try:
        # Prompt user to place their finger
        lcd.lcd_clear()
        lcd.lcd_display_string("Place Finger", 1, 0)
        sleep(1)

        # Show a message indicating the scanning process
        lcd.lcd_clear()
        lcd.lcd_display_string("Scanning Finger", 1, 0)
        sleep(1)

        # Capture fingerprint
        if not fingerprint_sensor.readImage():
            print('Failed to read fingerprint')
            return False

        fingerprint_sensor.convertImage(0x01)  # Convert to template
        position_number = fingerprint_sensor.searchTemplate()  # Search in the database

        if position_number[0] >= 0:
            # Query database to match PIN
            cursor.execute("SELECT ID FROM members WHERE PIN = %s", (pin_input,))
            pin_exists = cursor.fetchone()

            return pin_exists is not None

        return False

    except Exception as e:
        print('Error:', e)
        return False
def trigger_alarm():
    """Trigger the buzzer alarm for 10 seconds with 3-second intervals."""
    for _ in range(10):
        GPIO.output(buzzer, GPIO.HIGH)
        sleep(1)  # Buzzer on for 1 second
        GPIO.output(buzzer, GPIO.LOW)
        sleep(2)  # Buzzer off for 2 seconds

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
            # Show a message prompting for PIN input
            lcd.lcd_clear()
            lcd.lcd_display_string("Please Input PIN", 1, 0)
            sleep(1)
        else:
            # Check if the PIN exists in the database
            cursor.execute("SELECT ID FROM members WHERE PIN = %s", (input_pin,))
            pin_exists = cursor.fetchone()

            if pin_exists:
                # Show a message asking for fingerprint
                lcd.lcd_clear()
                lcd.lcd_display_string("Scanning Finger", 1, 0)
                sleep(1)

                if verify_fingerprint_and_pin(input_pin):
                    print("Fingerprint and PIN verified!")
                    lcd.lcd_clear()
                    lcd.lcd_display_string("Access Granted", 1, 0)

                    # Activate buzzer and relay
                    GPIO.output(buzzer, GPIO.HIGH)
                    sleep(0.3)  # Buzzer on for 0.3 seconds
                    GPIO.output(buzzer, GPIO.LOW)

                    GPIO.output(Relay, GPIO.LOW)
                    sleep(10)  # Keep door open for 3 seconds
                    GPIO.output(Relay, GPIO.HIGH)
                    
                    # Reset failed attempts counter
                    failed_attempts = 0
                else:
                    print("Fingerprint or PIN not recognized!")
                    lcd.lcd_clear()
                    lcd.lcd_display_string("Access Denied", 1, 0)
                    GPIO.output(buzzer, GPIO.HIGH)
                    sleep(0.3)
                    GPIO.output(buzzer, GPIO.LOW)
                    
                    # Increment failed attempts counter
                    failed_attempts += 1

                    # Check if failed attempts threshold is reached
                    if failed_attempts >= 3 and not alarm_triggered:
                        alarm_triggered = True
                        print("Triggering alarm!")
                        trigger_alarm()
                        sleep(10)  # Wait for 10 seconds before allowing further input
                        alarm_triggered = False
            else:
                print("PIN not found in database!")
                lcd.lcd_clear()
                lcd.lcd_display_string("PIN Not Found", 1, 0)
                GPIO.output(buzzer, GPIO.HIGH)
                sleep(0.3)
                GPIO.output(buzzer, GPIO.LOW)
                
                # Increment failed attempts counter
                failed_attempts += 1

                # Check if failed attempts threshold is reached
                if failed_attempts >= 3 and not alarm_triggered:
                    alarm_triggered = True
                    print("Triggering alarm!")
                    trigger_alarm()
                    sleep(10)  # Wait for 10 seconds before allowing further input
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
        print(input_pin)
        lcd.lcd_display_string(str(input_pin), 2, 0)
    if GPIO.input(R2) == 1:
        input_pin += characters[1]
        print(input_pin)
        lcd.lcd_display_string(str(input_pin), 2, 0)
    if GPIO.input(R3) == 1:
        input_pin += characters[2]
        print(input_pin)
        lcd.lcd_display_string(str(input_pin), 2, 0)
    if GPIO.input(R4) == 1:
        input_pin += characters[3]
        print(input_pin)
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
    # Ensure the connection and serial port are closed
    if conn.is_connected():
        conn.close()
    GPIO.cleanup()
