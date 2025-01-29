import RPi.GPIO as GPIO
import time

# Pin number for your line finder sensor SIN pin
INPUT_PIN = 2  # Replace with the GPIO number you're using

# GPIO setup
GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering (GPIO numbers)
GPIO.setup(INPUT_PIN, GPIO.IN)  # Set pin as input

try:
    while True:
        # Read the input pin value
        pin_value = GPIO.input(INPUT_PIN)
        
        if pin_value == GPIO.HIGH:  # Or simply if pin_value:
            print("Line detected!")
        else:
            print("No line detected.")
        
        time.sleep(0.1)  # Add a small delay to prevent spamming

except KeyboardInterrupt:
    print("Exiting program...")

finally:
    GPIO.cleanup()  # Reset GPIO pins on exit
