from flask import Flask, render_template, request, redirect, session, jsonify
from flask_mysqldb import MySQL
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.secret_key = "smart_ride_secret_key"

# ===== DATABASE =====
import os

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ===== HOME =====
@app.route('/')
def home():
    return redirect('/login')

# ===== LOGIN =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()

        if user:
            session['id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            return redirect('/dashboard')
        else:
            error = "Invalid credentials ❌"

    return render_template('login.html', error=error)
# ===== REGISTER =====
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)",
                       (name, email, password, role))
        mysql.connection.commit()
        cursor.close()

        return redirect('/login')

    return render_template('register.html')

# ===== DASHBOARD =====
@app.route('/dashboard')
def dashboard():
    if 'id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()
    cursor.execute("""
SELECT r.*,

(
    SELECT ROUND(AVG(rt.rating),1)
    FROM ratings rt
    WHERE rt.ride_id = r.id
) AS avg_rating,

(
    SELECT COUNT(*)
    FROM ratings rt
    WHERE rt.ride_id = r.id AND rt.user_id = %s
) AS already_rated,

(
    SELECT COUNT(*)
    FROM bookings b
    WHERE b.ride_id = r.id AND b.passenger_id = %s
) AS already_booked

FROM rides r
""", (session['id'], session['id']))

    rides = cursor.fetchall()
    cursor.close()

    return render_template('dashboard.html', 
                       rides=rides, 
                       user=session)
# ===== ADD RIDE =====
@app.route('/add_ride', methods=['POST'])
def add_ride():
    source = request.form['source']
    destination = request.form['destination']
    ride_date = request.form['ride_date']
    seats = request.form['seats']
    price = request.form['price']
    phone = request.form['phone']   # ✅ NEW

    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO rides (driver_id, source, destination, ride_date, seats, price, phone)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (session['id'], source, destination, ride_date, seats, price, phone))

    mysql.connection.commit()
    cursor.close()

    return redirect('/dashboard')
# ===== BOOK =====
@app.route('/book/<int:ride_id>')
def book(ride_id):
    if 'id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    # insert booking
    cursor.execute("""
        INSERT INTO bookings (ride_id, passenger_id)
        VALUES (%s, %s)
    """, (ride_id, session['id']))

    mysql.connection.commit()
    cursor.close()

    return redirect('/dashboard')
@app.route('/rate/<int:ride_id>', methods=['POST'])
def rate_ride(ride_id):
    if 'id' not in session:
        return redirect('/login')

    rating = request.form.get('rating')

    cursor = mysql.connection.cursor()

    # get driver id
    cursor.execute("SELECT driver_id FROM rides WHERE id=%s", (ride_id,))
    ride = cursor.fetchone()

    # insert rating
    cursor.execute("""
INSERT INTO ratings (ride_id, user_id, rating)
VALUES (%s, %s, %s)
""", (ride_id, session['id'], rating))

    mysql.connection.commit()
    cursor.close()

    return redirect('/dashboard')
# ===== LIVE LOCATION =====
@socketio.on('location')
def handle_location(data):
    emit('location', data, broadcast=True)
@app.route('/complete/<int:ride_id>')
def complete_ride(ride_id):
    if 'id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()

    cursor.execute("""
        UPDATE rides SET completed=1 WHERE id=%s AND driver_id=%s
    """, (ride_id, session['id']))

    mysql.connection.commit()
    cursor.close()

    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
# ===== AI CHATBOT =====
@app.route('/chatbot', methods=['POST'])
def chatbot():
    user_message = request.json.get('message').lower()

    cursor = mysql.connection.cursor()
    response = "Sorry, I didn't understand. Try asking about rides."

    # ===== GREETINGS =====
    if any(word in user_message for word in ["hi", "hello", "hey"]):
        response = "Hi 👋 How can I help you with rides?"

    # ===== THANK YOU =====
    elif "thank" in user_message:
        response = "You're welcome 😊 Happy riding!"

    # ===== HELP =====
    elif "help" in user_message:
        response = "You can ask me:\n• Available rides\n• Rides from a location\n• Cheapest rides"

    # ===== AVAILABLE RIDES =====
    elif "rides" in user_message or "available" in user_message:
        cursor.execute("SELECT source, destination, price FROM rides WHERE booked=0 LIMIT 5")
        rides = cursor.fetchall()

        if rides:
            response = "Available rides:\n"
            for r in rides:
                response += f"{r['source']} ➝ {r['destination']} ₹{r['price']}\n"
        else:
            response = "No rides available right now."

    # ===== FROM LOCATION =====
    elif "from" in user_message:
        word = user_message.split("from")[-1].strip()

        cursor.execute("""
            SELECT source, destination, price 
            FROM rides 
            WHERE source LIKE %s AND booked=0
            LIMIT 5
        """, ('%' + word + '%',))

        rides = cursor.fetchall()

        if rides:
            response = f"Rides from {word}:\n"
            for r in rides:
                response += f"{r['source']} ➝ {r['destination']} ₹{r['price']}\n"
        else:
            response = "No rides found."

    # ===== TO LOCATION =====
    elif "to" in user_message:
        word = user_message.split("to")[-1].strip()

        cursor.execute("""
            SELECT source, destination, price 
            FROM rides 
            WHERE destination LIKE %s AND booked=0
            LIMIT 5
        """, ('%' + word + '%',))

        rides = cursor.fetchall()

        if rides:
            response = f"Rides to {word}:\n"
            for r in rides:
                response += f"{r['source']} ➝ {r['destination']} ₹{r['price']}\n"
        else:
            response = "No rides found."

    # ===== CHEAP RIDES =====
    elif "cheap" in user_message or "low price" in user_message:
        cursor.execute("""
            SELECT source, destination, price 
            FROM rides 
            WHERE booked=0
            ORDER BY price ASC LIMIT 5
        """)
        rides = cursor.fetchall()

        if rides:
            response = "Cheapest rides:\n"
            for r in rides:
                response += f"{r['source']} ➝ {r['destination']} ₹{r['price']}\n"
        else:
            response = "No rides available."

    # ===== CONTACT =====
    elif "contact" in user_message or "phone" in user_message:
        response = "You can see driver phone number after booking the ride."

    # ===== GOODBYE =====
    elif "bye" in user_message:
        response = "Goodbye 👋 Have a safe ride!"

    cursor.close()
    return jsonify({"response": response})
# ===== RUN =====
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)