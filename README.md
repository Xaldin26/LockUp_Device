# LockUp Device - Installation Guide

## Overview
The LockUp Device is a security system that integrates a fingerprint sensor and a keypad for access control. This guide provides installation instructions and system requirements.

## System Requirements
### Hardware:
- Raspberry Pi / PC (with Python installed)
- AS608 Fingerprint Sensor
- 4x4 Keypad
- Relay Module (for lock control)
- Power Supply (suitable for your hardware)

### Software:
- Python 3.x
- Required Python libraries:
  ```sh
  pip install pyserial flask RPi.GPIO
  ```

## Installation Steps

### 1. Download the Repository
- Clone the repository from GitHub:
  ```sh
  git clone https://github.com/your-repository/LockUp_Device.git
  cd LockUp_Device
  ```

### 2. Install Dependencies
- Run the following command to install required libraries:
  ```sh
  pip install -r requirements.txt
  ```
  *(If `requirements.txt` is not available, install dependencies manually as listed above.)*

### 3. Configure the System
- Connect the fingerprint sensor and keypad to the appropriate GPIO pins.
- Modify the script if necessary to match your hardware configuration.

### 4. Running the System
- Ensure all necessary hardware components are connected.
- Open a terminal or command prompt in the project directory.
- Run the main security system script:
  ```sh
  python "Security system with keypad.py"
  ```

## Registering a Fingerprint
- Run the fingerprint registration script:
  ```sh
  python fingerprintregister.py
  ```
- Follow the on-screen instructions to scan and register a fingerprint.

## Access Control
- Users can unlock the system using either:
  1. A registered fingerprint.
  2. A PIN entered on the keypad.

## Admin Credentials
- The default **admin PIN** is: `1111`
- Entering this PIN will grant administrative access.
- The admin can manage user access and keep the lock open indefinitely until manually locked again.

## API Integration
- The system includes an API for external control.
- To run the API server:
  ```sh
  python api.py
  ```

## Notes
- Change the admin PIN for better security.
- Ensure the database is backed up regularly.
- Restart the system if any unexpected behavior occurs.

---
For further modifications or troubleshooting, check the source code and adjust settings as needed.

