from flask import Flask
import threading
import time
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

app = Flask(__name__)

def background_task():
    while True:
        print("🔄 Background thread is running...")
        time.sleep(1)

@app.route('/')
def home():
    return "✅ Flask is running with threading!"

if __name__ == '__main__':
    print("🟢 Starting background thread...")
    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()

    app.run(debug=False, host='0.0.0.0', port=5000)
