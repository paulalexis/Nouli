from flask import Flask, render_template, jsonify, request, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, DateTime, select, and_
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
import random
import os
import logging
import pytz

tz = pytz.timezone("Europe/Paris")  # or your local time zone

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)


# os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/activity_data'
os.environ['DATABASE_URL'] = 'postgresql://nouli_database_user:ZtVNvHUPyGHTsb8tIoo2vLPwpsPAx5MS@dpg-cudp9h3tq21c738ieur0-a.frankfurt-postgres.render.com/nouli_database'


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Set it as an environment variable!")

if DATABASE_URL.startswith("postgres://"):  # Render gives "postgres://", but SQLAlchemy expects "postgresql://"
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

latest_frame = None
frame_lock = threading.Lock()

db = SQLAlchemy(app)

class Activity(db.Model):
    id = Column(Integer, primary_key=True)
    time = Column(String, nullable=False)
    turns = Column(Integer, nullable=False)
    speed = Column(Float, nullable=False)

class SensorState(db.Model):
    id = Column(Integer, primary_key=True)
    previous_value = Column(Integer)
    previous_previous_value = Column(Integer)

class Histogram(db.Model):
    id = Column(Integer, primary_key=True)
    time_start = Column(String, nullable=False)
    interval_length = Column(Float, nullable=False)
    turns = Column(Integer, nullable=False)

perimeter = 0.6
interval_length_base = 60 * 30

def max(a, b):
    return a if a > b else b

def init_db():
    db.create_all()
    if not SensorState.query.first():
        sensor_state = SensorState(id=1, previous_value=0, previous_previous_value=0)
        db.session.add(sensor_state)
        db.session.commit()
    if not Histogram.query.first():
        histogram = Histogram(id=1, time_start=datetime.now(tz).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], interval_length=interval_length_base, turns=0)
        db.session.add(histogram)
        db.session.commit()

def add_entries_to_histogram():
    now = datetime.now(tz)
    today = now.strftime('%Y/%m/%d')

    if now.hour < 12:
        start_time = f"{today} 00:00:00.000"
        end_time = f"{today} 12:00:00.000"
    else:
        start_time = f"{today} 12:00:00.000"
        end_time = f"{today} 23:59:59.999"

    # Check if any entry exists in the given time range
    exists = db.session.query(Histogram.id).filter(
        and_(
            Histogram.time_start >= start_time,
            Histogram.time_start < end_time
        )
    ).first()

    if not exists:
        print(f"No entries found between {start_time} and {end_time}. Creating entries...")

        interval_length = 30 * 60
        entries = []
        current_time = datetime.strptime(start_time, "%Y/%m/%d %H:%M:%S.%f")

        while current_time < datetime.strptime(end_time, "%Y/%m/%d %H:%M:%S.%f"):
            entries.append(
                Histogram(
                    time_start=current_time.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3],  # Trim to milliseconds
                    interval_length=interval_length,
                    turns=0
                )
            )
            current_time += timedelta(minutes=30)

        db.session.bulk_save_objects(entries)
        db.session.commit()
        print("Entries created successfully.")
    else:
        print(f"Entries already exist between {start_time} and {end_time}.")

# def insert_turns_to_db():
#     print("🚀 insert_turns_to_db() STARTED!") 
#     new_entry = None  # Initialize new_entry so it's always defined
#     try:
#         last_activity = Activity.query.order_by(Activity.id.desc()).first()

#         if last_activity:
#             turns0, time0_str = last_activity.turns, last_activity.time
#             time0 = datetime.strptime(time0_str, '%Y/%m/%d %H:%M:%S.%f').timestamp()
#         else:
#             turns0, time0 = 0, time.time()

#         time_now = time.time()
#         speed = perimeter / (2 * max(time_now - time0, 0.001))  # Avoid division by zero
#         timestamp = datetime.now(tz).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]

#         new_activity = Activity(time=timestamp, turns=turns0 + 1, speed=round(speed, 3))
#         db.session.add(new_activity)

#         # Execute subquery to get the last 20 IDs and clean the database
#         subq_results = db.session.query(Activity.id).order_by(Activity.id.desc()).limit(20).all()
#         id_list = [result[0] for result in subq_results]
#         db.session.query(Activity).filter(Activity.id.notin_(id_list)).delete(synchronize_session='fetch')

#         # Update Histogram Table
#         last_row = Histogram.query.order_by(Histogram.id.desc()).first()
#         if not last_row:
#             new_entry = Histogram(
#                 time_start=timestamp,
#                 interval_length=interval_length_base,
#                 turns=1
#             )
#             db.session.add(new_entry)
#         else:
#             try:
#                 time_start_int = datetime.strptime(last_row.time_start, '%Y/%m/%d %H:%M:%S.%f').timestamp()
#                 if time_start_int + last_row.interval_length > time_now:
#                     last_row.turns += 1
#                 else:
#                     new_entry = Histogram(
#                         time_start=datetime.fromtimestamp(time_start_int + last_row.interval_length).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3],
#                         interval_length=interval_length_base,
#                         turns=1
#                     )
#                     db.session.add(new_entry)
#             except ValueError:
#                 print("Error parsing time_start in Histogram. Resetting.")
#                 new_entry = Histogram(
#                     time_start=timestamp,
#                     interval_length=interval_length_base,
#                     turns=1
#                 )
#                 db.session.add(new_entry)
#         db.session.commit()
#     except SQLAlchemyError as e:
#         db.session.rollback()
#         print(f"SQLAlchemy Error: {str(e)}")


# def monitor_line_sensor():
#     print("✅ monitor_line_sensor started!")  # Debugging print
#     while True:
#         try:
#             with app.app_context():
#                 print("✅ Calling insert_turns_to_db()")  # Debugging print
#                 insert_turns_to_db()
#         except Exception as e:
#             print(f"Error while monitoring the sensor: {e}")
#         time.sleep(0.5)

# def monitor_line_sensor():
#     while True:
#         try:
#             # Make sure app context is active
#             with app.app_context():              
#                 value = int(time.time() * 1000) % 2  # Dummy sensor value

#                 sensor_state = db.session.get(SensorState, 1)
#                 if sensor_state:
#                     previous_value = sensor_state.previous_value
#                     previous_previous_value = sensor_state.previous_previous_value
#                 else:
#                     previous_value = previous_previous_value = 0

#                 # Check if there's a valid turn event
#                 if (previous_value == value) and (previous_value != previous_previous_value):
#                     insert_turns_to_db()  # Insert the turn event into DB

#                 # Update the sensor state table
#                 if sensor_state:
#                     sensor_state.previous_previous_value = previous_value
#                     sensor_state.previous_value = value
#                     db.session.commit()

#         except Exception as e:
#             print(f"Error while monitoring the sensor: {e}")

#         time.sleep(0.5)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """Receive and store an image from the Raspberry Pi."""
    global latest_frame
    if 'image' in request.files:
        image_file = request.files['image']
        image_bytes = image_file.read()

        # Store the image in a global variable (thread-safe with lock)
        with frame_lock:
            latest_frame = image_bytes
        return 'Image received', 200
    return 'No image received', 400

def generate_stream():
    """Generate MJPEG stream of the latest frame."""
    while True:
        if latest_frame:
            with frame_lock:
                frame = latest_frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: %d\r\n\r\n' % len(frame) + frame + b'\r\n')
        time.sleep(0.01)  # Reduced sleep time to allow faster frame updates

@app.route('/stream.mjpg')
def stream():
    """Route to stream the MJPEG."""
    return Response(generate_stream(), 
                    content_type='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-cache'})

@app.route('/activityhistory')
def activityHistoryPage():
    return render_template('activityhistory.html')

@app.route('/data')
def data():
    try:
        # Fetch the two most recent activities using SQLAlchemy
        last_two_rows = Activity.query.order_by(Activity.id.desc()).limit(2).all()

        if last_two_rows:
            # If there's only one row, use its speed
            if len(last_two_rows) == 1:
                speed = last_two_rows[0].speed
            else:
                # If there are two rows, calculate the average speed
                speed = (last_two_rows[0].speed + last_two_rows[1].speed) / 2
            turns = last_two_rows[0].turns
            time = last_two_rows[0].time

            last_turn_time = datetime.strptime(last_two_rows[0].time, "%Y/%m/%d %H:%M:%S.%f").astimezone(tz)

            current_time = datetime.now(tz)
            if current_time - last_turn_time > timedelta(seconds=3):
                speed = 0
        else:
            turns, time, speed = 0, datetime.now(tz).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], 0

        # Return the computed data as JSON
        return jsonify({
            'turns': turns,
            'speed': round(speed, 2),
            'time_turn': time
        })
    except Exception as e:
        print(f"Error while fetching data: {e}")
        return jsonify({"error": "An error occurred while fetching data."})

@app.route('/last_20_entries')
def get_last_20_entries():
    try:
        entries = Activity.query.limit(20).all()
        data = [{"time": entry.time, "turns": entry.turns, "speed": entry.speed} for entry in entries]

        return jsonify({'entries': data})
    except Exception as e:
        print(f"Error while fetching last 20 entries: {e}")
        return jsonify({"error": "An error occurred while fetching the last 20 entries."})

@app.route('/coHistoryBits')
def history_bits():
    try:
        # Fetch all rows from the sensor_state table using SQLAlchemy
        rows = SensorState.query.order_by(SensorState.id.desc()).all()

        # Prepare the data to return
        data = [{"id": row.id, "previous_value": row.previous_value, "previous_previous_value": row.previous_previous_value} for row in rows]

        return jsonify({"data": data})
    except Exception as e:
        print(f"Error while fetching sensor state: {e}")
        return jsonify({"error": "An error occurred while fetching sensor state."})

@app.route('/coHistogram')
def get_histogram_data():
    try:
        now = datetime.now(tz)
        today = now.strftime('%Y/%m/%d')

        if now.hour < 12:
            # Before noon: Get data from midnight to 11:30 AM of today
            start_time = f"{today} 00:00:00.000"
            end_time = f"{today} 12:00:00.000"
        else:
            # After noon: Get data from 12:00 PM to 11:30 PM of today
            start_time = f"{today} 12:00:00.000"
            end_time = f"{today} 23:59:59.999"

        # Fetch histogram data for the relevant time range
        rows = Histogram.query.filter(
            and_(
                Histogram.time_start >= start_time,
                Histogram.time_start < end_time
            )
        ).order_by(Histogram.time_start).all()

        # Prepare response data
        data = [{"time_start": row.time_start, "turns": row.turns} for row in rows]

        # Fetch the most recent turn from the activity table
        last_activity = Activity.query.order_by(Activity.id.desc()).first()
        turns = last_activity.turns if last_activity else 0

        return jsonify({
            'data': data,
            'last_turns': turns,
            'interval_size': interval_length_base
        })

    except Exception as e:
        print(f"Error while fetching histogram data: {e}")
        return jsonify({"error": "An error occurred while fetching histogram data."})

@app.route('/clear_data')
def clear_histogram():
    try:
        db.drop_all()
        db.create_all()
        return jsonify({"message": "Tables have been cleared successfully."}), 200
    except Exception as e:
        print(f"Error while clearing data: {e}")
        return jsonify({"error": "An error occurred while clearing data."}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    # threading.Thread(target=monitor_line_sensor, daemon=True).start()
    app.run(debug=False, host='0.0.0.0', port=5000)