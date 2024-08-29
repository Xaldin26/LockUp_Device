import tkinter as tk
from tkinter import messagebox
from tkinter import font
from PIL import Image, ImageTk  # Import Image and ImageTk from Pillow
from pyfingerprint.pyfingerprint import PyFingerprint
import requests
import base64

# Initialize fingerprint sensor
try:
    f = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)

    if not f.verifyPassword():
        raise ValueError('The given fingerprint sensor password is wrong!')

except Exception as e:
    print('The fingerprint sensor could not be initialized!')
    print('Exception message: ' + str(e))
    exit(1)

# API URL
API_URL = "http://192.168.1.16:8000/api/instructors/{}"  # Replace with your API endpoint

# GUI setup
root = tk.Tk()
root.title("User Registration and Management")
root.geometry("800x600")  # Increase the window size to accommodate new elements
root.configure(bg="#f4f4f9")  # Light background color for a clean look

# Load and resize the logo
try:
    logo_image = Image.open("logo.png")
    logo_image = logo_image.resize((700, 160), Image.LANCZOS)  
    logo = ImageTk.PhotoImage(logo_image)
except Exception as e:
    print("Error loading or resizing the logo:", e)
    logo = None

# Add the logo to the window
logo_label = tk.Label(root, image=logo, bg="#f4f4f9")
logo_label.pack(pady=(10, 0))  

# Define custom fonts and colors
title_font = font.Font(family="Arial", size=20, weight="bold")
label_font = font.Font(family="Arial", size=16, weight="bold")
entry_font = font.Font(family="Arial", size=14)
button_font = font.Font(family="Arial", size=16, weight="bold")
frame_bg = "#ffffff"  
button_bg = "#004d99"  
button_fg = "#ffffff"  
border_color = "#dddddd"  

def register_fingerprint():
    try:
        print('Waiting for finger...')
        while not f.readImage():
            pass

        f.convertImage(0x01)

        result = f.searchTemplate()
        positionNumber = result[0]

        if positionNumber >= 0:
            messagebox.showwarning("Warning", "Fingerprint already registered!")
            return

        f.createTemplate()
        positionNumber = f.storeTemplate()
        
        # Download the characteristics of the template to store as BLOB
        f.loadTemplate(positionNumber, 0x01)
        characteristics = f.downloadCharacteristics(0x01)
        fingerprint_blob = bytearray(characteristics)
        
        messagebox.showinfo("Success", f"Fingerprint registered at position {positionNumber}")

        return positionNumber, fingerprint_blob

    except Exception as e:
        messagebox.showerror("Error", f"Operation failed! {str(e)}")

def register():
    email = email_entry.get().strip()
    pin = pin_entry.get().strip()

    if not email or not pin:
        messagebox.showwarning("Input Error", "Email and PIN are required!")
        return

    if not pin.isdigit() or len(pin) != 4:
        messagebox.showwarning("Input Error", "PIN must be a 4-digit number!")
        return

    result = register_fingerprint()
    if result is not None:
        finger_id, fingerprint_blob = result

        fingerprint_blob_base64 = base64.b64encode(fingerprint_blob).decode('utf-8')

        payload = {
            'finger_id': finger_id,
            'pin': int(pin),
            'fingerprint_template': fingerprint_blob_base64
        }

        api_url = API_URL.format(email)

        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.put(api_url, json=payload, headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                messagebox.showinfo("Success", "User registered successfully!")
            else:
                messagebox.showerror("Error", f"Failed to register user: {response.text}")

        except requests.HTTPError as http_err:
            try:
                error_message = response.json().get('errors', response.text)
            except requests.JSONDecodeError:
                error_message = response.text
            print(f"HTTP error occurred: {error_message}")
            messagebox.showerror("HTTP Error", f"Failed to send data to API: {error_message}")
        except requests.RequestException as e:
            messagebox.showerror("Network Error", f"Failed to send data to API: {str(e)}")
            print("Network Error", f"Failed to send data to API: {str(e)}")

def delete_fingerprint():
    try:
        position = int(delete_position_entry.get().strip())

        if position < 0 or position > 149:
            messagebox.showwarning("Input Error", "Position must be between 0 and 149!")
            return

        f.deleteTemplate(position)
        messagebox.showinfo("Success", f"Fingerprint at position {position} deleted successfully!")

    except ValueError:
        messagebox.showwarning("Input Error", "Invalid position. Please enter a number between 0 and 149.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete fingerprint: {str(e)}")

# Create and place widgets
root.title_frame = tk.Frame(root, bg="#004d99", padx=20, pady=10)
root.title_frame.pack(fill="x")

title_label = tk.Label(root.title_frame, text="MAC Laboratory", font=title_font, bg="#004d99", fg="#ffffff")
title_label.pack()

frame = tk.Frame(root, bg=frame_bg, padx=30, pady=30, relief="flat")
frame.pack(padx=30, pady=30, fill="both", expand=True)

tk.Label(frame, text="Email:", font=label_font, bg=frame_bg, anchor="w").grid(row=1, column=0, padx=10, pady=10, sticky="w")
email_entry = tk.Entry(frame, font=entry_font, bd=2, relief="solid", bg="#ffffff", fg="#333333")
email_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

tk.Label(frame, text="Enter PIN:", font=label_font, bg=frame_bg, anchor="w").grid(row=2, column=0, padx=10, pady=10, sticky="w")
pin_entry = tk.Entry(frame, show="*", font=entry_font, bd=2, relief="solid", bg="#ffffff", fg="#333333")
pin_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

register_button = tk.Button(frame, text="Register", font=button_font, bg=button_bg, fg=button_fg, bd=0, relief="flat", command=register)
register_button.grid(row=3, column=0, columnspan=2, pady=20)

# Frame for deletion section
delete_frame = tk.Frame(root, bg=frame_bg, padx=10, pady=10, relief="flat")
delete_frame.pack(padx=10, pady=10, fill="both", expand=True)

tk.Label(delete_frame, text="Position to Delete:", font=label_font, bg=frame_bg, anchor="w").grid(row=1, column=0, padx=10, pady=10, sticky="w")
delete_position_entry = tk.Entry(delete_frame, font=entry_font, bd=2, relief="solid", bg="#ffffff", fg="#333333")
delete_position_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

delete_button = tk.Button(delete_frame, text="Delete Fingerprint", font=button_font, bg=button_bg, fg=button_fg, bd=0, relief="flat", command=delete_fingerprint)
delete_button.grid(row=2, column=0, columnspan=2, pady=20)

# Configure grid column weights for better resizing
frame.grid_columnconfigure(1, weight=1)
delete_frame.grid_columnconfigure(1, weight=1)

# Style adjustments for the frames
frame.config(highlightbackground=border_color, highlightcolor=border_color, highlightthickness=1)
delete_frame.config(highlightbackground=border_color, highlightcolor=border_color, highlightthickness=1)

root.mainloop()
