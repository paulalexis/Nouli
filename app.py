from flask import Flask, render_template, jsonify
import threading
import time
from datetime import datetime
import sqlite3
import random
import psycopg2
import os

# os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/activity_data'

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Set it as an environment variable!")

# Initialize Flask app
app = Flask(__name__)
perimeter = 0.6
interval_length_base = 60*30

def max(a, b):
    return a if a > b else b

# Initialize database
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Create activity table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity (
                id SERIAL PRIMARY KEY,
                time TEXT NOT NULL,
                turns INTEGER NOT NULL,
                speed REAL NOT NULL
            )
        ''')

        cursor.execute("SELECT COUNT(*) FROM activity")
        row_count = cursor.fetchone()[0]

        if row_count == 0:
            cursor.execute("INSERT INTO activity (time, turns, speed) VALUES (%s, %s, %s)", 
                        (datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], 0, 0.0))
            conn.commit()
        
        # Create a table to store the last 3 sensor values (value, previous_value, previous_previous_value)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_state (
                id SERIAL PRIMARY KEY,
                previous_value INTEGER,
                previous_previous_value INTEGER
            )
        ''')
        conn.commit()

        # Insert initial sensor state values into the table
        cursor.execute('''
            INSERT INTO sensor_state (id, previous_value, previous_previous_value)
            VALUES (1, 0, 0)
            ON CONFLICT (id) 
            DO UPDATE SET previous_value = EXCLUDED.previous_value, 
                        previous_previous_value = EXCLUDED.previous_previous_value;
        ''')
        conn.commit()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS histogram (
                id SERIAL PRIMARY KEY,
                time_start TEXT NOT NULL,
                interval_length REAL NOT NULL,
                turns INTEGER NOT NULL
            )
        ''')
        conn.commit()

    except Exception as e:
        print(f"Error during database initialization: {e}")

# Insert turns to the database
def insert_turns_to_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Fetch the most recent row
        cursor.execute("SELECT turns, time FROM activity ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()

        if last_row:
            turns0, time0_str = last_row
            # Convert string timestamp to a Unix timestamp
            time0 = time.mktime(datetime.strptime(time0_str, '%Y/%m/%d %H:%M:%S.%f').timetuple())
        else:
            # Default values if table is empty
            turns0, time0 = 0, time.time()

        # Compute new values
        turns = turns0 + 1
        time_now = time.time()
        speed = perimeter / (2 * max(time_now - time0, 0.001))
        timestamp = datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]

        # Insert the new row
        cursor.execute('''
            INSERT INTO activity (turns, time, speed)
            VALUES (%s, %s, %s)
        ''', (turns, timestamp, round(speed, 3)))
        conn.commit()

        # Keep only the last 20 records
        cursor.execute('''
            DELETE FROM activity WHERE id NOT IN (
                SELECT id FROM activity ORDER BY id DESC LIMIT 20
            )
        ''')
        conn.commit()

        cursor.execute("SELECT id, time_start, interval_length, turns FROM histogram ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()

        if not last_row:
            cursor.execute('''
                    INSERT INTO histogram (time_start, interval_length, turns)
                    VALUES (%s, %s, %s)
                ''', (datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], interval_length_base, 1))
            conn.commit()
        else:
            id, time_start, interval_length, turns_tot = last_row
            time_start_int = datetime.strptime(time_start, '%Y/%m/%d %H:%M:%S.%f').timestamp()
            if time_start_int + interval_length > time.time():
                cursor.execute('''
                    UPDATE histogram 
                    SET turns = %s
                    WHERE id = %s
                ''', (turns_tot + 1, id))
                conn.commit()
            else:
                cursor.execute('''
                    INSERT INTO histogram (time_start, interval_length, turns)
                    VALUES (%s, %s, %s)
                ''', (datetime.fromtimestamp(time_start_int + interval_length).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3], interval_length_base, 1))
                conn.commit()

        conn.close()
    except Exception as e:
        print(f"Error while inserting turns into DB: {e}")

# Monitor the line sensor
def monitor_line_sensor():    
    while True:
        try:
            value = random.randint(0, 1) * random.randint(0, 1)
            
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()

            cursor.execute('SELECT previous_value, previous_previous_value FROM sensor_state WHERE id = 1')
            row = cursor.fetchone()
            if row:
                previous_value, previous_previous_value = row
            else:
                previous_value = previous_previous_value = 0

            # Check if there's a valid turn event (simple logic as an example)
            if (previous_value == value) and (previous_value != previous_previous_value):
                insert_turns_to_db()
            
            # Update the sensor state table with the new values
            cursor.execute('''
                UPDATE sensor_state 
                SET previous_previous_value = %s, previous_value = %s
                WHERE id = 1
            ''', (previous_value, value))
            conn.commit()

            conn.close()
        except Exception as e:
            print(f"Error while monitoring the sensor: {e}")
        
        time.sleep(0.5)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Fetch the most recent row
        cursor.execute("SELECT turns, time, speed FROM activity ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()

        if last_row:
            turns, time, speed = last_row
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
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT time, turns, speed FROM activity LIMIT 20
        ''')
        data = cursor.fetchall()
        conn.close()

        return {'entries': data}
    except Exception as e:
        print(f"Error while fetching last 20 entries: {e}")
        return jsonify({"error": "An error occurred while fetching the last 20 entries."})

@app.route('/coHistoryBits')
def history_bits():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sensor_state ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        return jsonify({"data": rows})
    except Exception as e:
        print(f"Error while fetching sensor state: {e}")
        return jsonify({"error": "An error occurred while fetching sensor state."})

@app.route('/coHistogram')
def get_histogram_data():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        today = datetime.now().strftime('%Y/%m/%d')
        cursor = conn.cursor()

        # Fetch histogram data for today's date
        cursor.execute('''
            SELECT time_start, turns 
            FROM histogram 
            WHERE time_start LIKE %s
            ORDER BY time_start
        ''', (f'{today}%',))  # '%' is a wildcard for the entire day
        
        rows = cursor.fetchall()
        
        # Prepare the response data
        data = []
        for row in rows:
            data.append({
                'time_start': row[0],
                'turns': row[1],
            })
        
        cursor.execute("SELECT turns FROM activity ORDER BY id DESC LIMIT 1")
        actual_turn = cursor.fetchone()
        turns = actual_turn if actual_turn else 0

        conn.close()
        
        return {'data': data, 'last_turns': turns, 'interval_size': interval_length_base}
    except Exception as e:
        print(f"Error while fetching histogram data: {e}")
        return jsonify({"error": "An error occurred while fetching histogram data."})

@app.route('/clear_data')
def clear_histogram():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM histogram")
        cursor.execute("DELETE FROM activity")
        cursor.execute("DELETE FROM sensor_state")
        conn.commit()
        conn.close()

        return jsonify({"message": "Data has been cleared successfully."}), 200
    except Exception as e:
        print(f"Error while clearing data: {e}")
        return jsonify({"error": "An error occurred while clearing data."}), 500

# Start the background thread and run Flask app
if __name__ == '__main__':
    try:
        init_db()  # Initialize the database
        threading.Thread(target=monitor_line_sensor, daemon=True).start()  # Start background thread
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error starting the application: {e}")
