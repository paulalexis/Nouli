from flask import Flask, render_template
import RPi.GPIO as GPIO
import threading
import time

# Set up the GPIO pin
LINE_SENSOR_PIN = 2  # Set to GPIO pin 2
GPIO.setmode(GPIO.BCM)
GPIO.setup(LINE_SENSOR_PIN, GPIO.IN)

# Initialize Flask
app = Flask(__name__)

# Variable for turn count
turns = 0
previous_value = 0
previous_previous_value = 0
value = 0

# Variable for the speed and time stuff
time_turn = 0
speed = 0

# Constant Variables
perimeter = 0.6

def max(a,b):
    if a>b:
        return a
    return b

# Function to monitor the line sensor
def monitor_line_sensor():
    global turns, value, previous_value, previous_previous_value, perimeter, time_turn, speed
    while True:
        value = GPIO.input(LINE_SENSOR_PIN)
        if ((previous_value == value) and (previous_value != previous_previous_value)):
            turns += 1
            speed = perimeter/(2*max(time.time() - time_turn, 0.001))
            time_turn = time.time()
        previous_previous_value = previous_value
        previous_value = value
        print(f"Line detected: {value}, Nb turns: {turns}")  # Print status to the terminal
        time.sleep(0.05)  # Poll every 100 ms

@app.route('/')
def index():
    return render_template('index.html')  # Serve the main HTML page

@app.route('/data')
def data():
    global turns, time_turn, speed
    """Send current content"""
    return {'turns': turns, 'speed': speed, 'time_turn': time.time() - time_turn}

# Start the background thread and run the Flask app
if __name__ == '__main__':
    threading.Thread(target=monitor_line_sensor, daemon=True).start()  # Start background thread for sensor monitoring
    app.run(ssl_context='adhoc', debug=True, host='0.0.0.0', port=5000)  # Run the app on all IP addresses at port 5000
