from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, DateTime, select
import threading
import time
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
import random
import os
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)


# os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/activity_data'


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Set it as an environment variable!")

if DATABASE_URL.startswith("postgres://"):  # Render gives "postgres://", but SQLAlchemy expects "postgresql://"
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
        histogram = Histogram(id=1, time_start=datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], interval_length=interval_length_base, turns=0)
        db.session.add(histogram)
        db.session.commit()

def insert_turns_to_db():
    last_activity = Activity.query.order_by(Activity.id.desc()).first()

    if last_activity:
        turns0, time0_str = last_activity.turns, last_activity.time
        time0 = datetime.strptime(time0_str, '%Y/%m/%d %H:%M:%S.%f').timestamp()  # More accurate timestamp conversion
    else:
        turns0, time0 = 0, time.time()

    time_now = time.time()
    speed = perimeter / (2 * max(time_now - time0, 0.001))  # Avoid division by zero
    timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]

    new_activity = Activity(time=timestamp, turns=turns0 + 1, speed=round(speed, 3))
    db.session.add(new_activity)

    # Step 1: Execute subquery to get the last 20 IDs
    subq_results = db.session.query(Activity.id).order_by(Activity.id.desc()).limit(20).all()

    # Step 2: Extract the IDs from the subquery result (subq_results is a list of tuples)
    id_list = [result[0] for result in subq_results]

    # Step 3: Delete records where the ID is not in the list of the last 20 IDs
    db.session.query(Activity).filter(Activity.id.notin_(id_list)).delete(synchronize_session='fetch')


    # Update Histogram Table
    last_row = Histogram.query.order_by(Histogram.id.desc()).first()
    if not last_row:
        new_entry = Histogram(
            time_start=timestamp,
            interval_length=interval_length_base,
            turns=1
        )
        db.session.add(new_entry)
    else:
        try:
            time_start_int = datetime.strptime(last_row.time_start, '%Y/%m/%d %H:%M:%S.%f').timestamp()
            
            if time_start_int + last_row.interval_length > time_now:
                last_row.turns += 1
            else:
                new_entry = Histogram(
                    time_start=datetime.fromtimestamp(time_start_int + last_row.interval_length).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3],
                    interval_length=interval_length_base,
                    turns=1
                )
                db.session.add(new_entry)
        except ValueError:
            print("Error parsing time_start in Histogram. Resetting.")
            new_entry = Histogram(
                time_start=timestamp,
                interval_length=interval_length_base,
                turns=1
            )
            db.session.add(new_entry)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        print("❌ Error: ", e)


def monitor_line_sensor():
    while True:
        try:
            with app.app_context():
                # value = random.randint(0, 1) * random.randint(0, 1)
                value = int(time.time()*1000) % 2

                # Fetch the current sensor state using SQLAlchemy
                sensor_state = db.session.get(SensorState, 1)
                if sensor_state:
                    previous_value = sensor_state.previous_value
                    previous_previous_value = sensor_state.previous_previous_value
                else:
                    previous_value = previous_previous_value = 0

                # Check if there's a valid turn event
                if (previous_value == value) and (previous_value != previous_previous_value):
                    insert_turns_to_db()  # Insert the turn event into DB

                # Update the sensor state table
                if sensor_state:
                    sensor_state.previous_previous_value = previous_value
                    sensor_state.previous_value = value
                    db.session.commit()

        except Exception as e:
            print(f"Error while monitoring the sensor: {e}")

        time.sleep(0.5)

@app.route('/')
def index():
    return render_template('index.html')

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
        else:
            turns, time, speed = 0, datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], 0

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

        return {'entries': data}
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
        today = datetime.now().strftime('%Y/%m/%d')

        # Fetch histogram data for today's date using SQLAlchemy
        rows = Histogram.query.filter(Histogram.time_start.like(f'{today}%')).order_by(Histogram.time_start).all()

        # Prepare the response data
        data = [{"time_start": row.time_start, "turns": row.turns} for row in rows]

        # Fetch the most recent turn from the activity table
        last_activity = Activity.query.order_by(Activity.id.desc()).first()
        turns = last_activity.turns if last_activity else 0

        # Return the data as JSON
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
    threading.Thread(target=monitor_line_sensor, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=5000)
