import sqlite3

# Function to initialize the database
def init_db():
    # Connect to the SQLite database (this will create the file if it doesn't exist)
    conn = sqlite3.connect('activity_data.db')
    cursor = conn.cursor()

    # Create the table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS turns_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turns INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

# Call the function to initialize the database when the app starts
init_db()
