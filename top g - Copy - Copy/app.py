from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///politicians.db'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.secret_key = 'BARRACKHUSSEINOBAMANOCAPONAFATSTACK'
db = SQLAlchemy(app)

class Politician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    party = db.Column(db.String(100))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(100))
    running_for_governor = db.Column(db.Boolean, default=False)
    running_for_senate_position1 = db.Column(db.Boolean, default=False)
    running_for_senate_position2 = db.Column(db.Boolean, default=False)
    running_for_representative = db.Column(db.Boolean, default=False)

    def __init__(self, name, gender, party, bio, avatar):
        self.name = name
        self.gender = gender
        self.party = party
        self.bio = bio
        self.avatar = avatar

class State(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    population = db.Column(db.Integer)
    social_stance = db.Column(db.String(100))
    economic_stance = db.Column(db.String(100))
    governor_salary = db.Column(db.Integer)
    senator_salary = db.Column(db.Integer)
    lt_governor_salary = db.Column(db.Integer)
    representative_salary = db.Column(db.Integer)
    ranked_choice_voting = db.Column(db.Boolean)
    term_limit = db.Column(db.Integer)

    def __init__(self, name, population, social_stance, economic_stance, governor_salary,
                 senator_salary, lt_governor_salary, representative_salary, ranked_choice_voting, term_limit):
        self.name = name
        self.population = population
        self.social_stance = social_stance
        self.economic_stance = economic_stance
        self.governor_salary = governor_salary
        self.senator_salary = senator_salary
        self.lt_governor_salary = lt_governor_salary
        self.representative_salary = representative_salary
        self.ranked_choice_voting = ranked_choice_voting
        self.term_limit = term_limit

@app.route('/')
def index():
    politicians = Politician.query.all()
    politician = Politician.query.filter_by(name=session.get('username')).first()
    return render_template('index.html', politicians=politicians, politician=politician)

@app.route('/create_politician', methods=['GET', 'POST'])
def create_politician():
    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        party = request.form['party']
        bio = request.form['bio']
        avatar = request.files['avatar']

        filename = secure_filename(avatar.filename)
        avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        politician = Politician(name, gender, party, bio, filename)
        db.session.add(politician)
        db.session.commit()

        return redirect(f'/profile/{politician.id}')

    return render_template('create_politician.html')

@app.route('/profile/<int:politician_id>')
def profile(politician_id):
    politician = Politician.query.get(politician_id)
    return render_template('profile.html', politician=politician)

def get_state_data(state_id):
    if state_id == 1:
        state_data = {
            'name': 'California',
            'population': 39538223,
            'social_stance': 'Progressive',
            'economic_stance': 'Mixed',
            'governor_salary': '$210,000',
            'senator_salary': '$174,000',
            'lt_governor_salary': '$151,127',
            'representative_salary': '$174,000',
            'ranked_choice_voting': 'No',
            'term_limit': 'None',
            'governor': {
                'id': 14,
            },
            'lt_governor': {
                'id': 15,
            },
            'senator1': {
                'id': 16,
                'senate_class': '1'
            },
            'senator2': {
                'id': 17,
                'senate_class': '3'
            },
            'representative': {
                'id': 13,
                'seat_count': '53'
            }
        }
    elif state_id == 2:
        state_data = {
            'name': 'New York',
            'population': 19530351,
            'social_stance': 'Liberal',
            'economic_stance': 'Mixed',
            'governor_salary': '$225,000',
            'senator_salary': '$174,000',
            'lt_governor_salary': '$151,500',
            'representative_salary': '$174,000',
            'ranked_choice_voting': 'No',
            'term_limit': 'None',
            'governor': {
                'id': 18,
            },
            'lt_governor': {
                'id': 19,
            },
            'senator1': {
                'id': 20,
                'senate_class': '3'
            },
            'senator2': {
                'id': 21,
                'senate_class': '1'
            },
            'representative': {
                'id': 22,
                'seat_count': '1'
            }
        }
    else:
        return None

    # Fetch the usernames from user profiles based on the IDs
    governor_id = state_data['governor']['id']
    lt_governor_id = state_data['lt_governor']['id']
    senator1_id = state_data['senator1']['id']
    senator2_id = state_data['senator2']['id']
    representative_id = state_data['representative']['id']

    governor = Politician.query.get(governor_id)
    lt_governor = Politician.query.get(lt_governor_id)
    senator1 = Politician.query.get(senator1_id)
    senator2 = Politician.query.get(senator2_id)
    representative = Politician.query.get(representative_id)

    # Update the state data with the usernames
    state_data['governor']['username'] = governor.name if governor else None
    state_data['lt_governor']['username'] = lt_governor.name if lt_governor else None
    state_data['senator1']['username'] = senator1.name if senator1 else None
    state_data['senator2']['username'] = senator2.name if senator2 else None
    state_data['representative']['username'] = representative.name if representative else None

    return state_data

# Define the state route
@app.route('/state/<int:state_id>')
def state(state_id):
    state_data = get_state_data(state_id)

    # Retrieve the logged-in politician based on the session username
    politician = None
    if 'username' in session:
        politician = Politician.query.filter_by(name=session['username']).first()

    return render_template('state.html', state=state_data, politician=politician)

@app.route('/enter_primary', methods=['GET', 'POST'])
def enter_primary():
    if request.method == 'POST':
        # Retrieve the logged-in politician based on the session username
        politician = Politician.query.filter_by(name=session['username']).first()

        # Check if the politician is already running for any position
        if politician and not (politician.running_for_governor or politician.running_for_senate_position1 or politician.running_for_senate_position2 or politician.running_for_representative):
            position = request.form['position']

            # Update the politician's record in the database based on the selected position
            if position == 'Governor':
                politician.running_for_governor = True
            elif position == 'Senate Class 1':
                politician.running_for_senate_position1 = True
            elif position == 'Senate Class 2':
                politician.running_for_senate_position2 = True
            elif position == 'Representative':
                politician.running_for_representative = True

            db.session.commit()

        return redirect('/')  # Redirect to the home page after form submission

    return render_template('state.html')

@app.route('/enter_general_election', methods=['GET', 'POST'])
def enter_general_election():
    if request.method == 'POST':
        # Handle the form submission for the 'enter_general_election' endpoint
        # You can add your own implementation here

        return redirect('/')  # Redirect to the home page after form submission

    return render_template('enter_general_election.html')

@app.route('/login', methods=['GET', 'POST'])

@app.route('/join_primary/governor', methods=['POST'])
def join_primary_governor():
    if request.method == 'POST':
        # Retrieve the logged-in politician based on the session username
        politician = Politician.query.filter_by(name=session['username']).first()

        # Check if the politician is already running for any position
        if politician and not (politician.running_for_governor or politician.running_for_senate_position1 or politician.running_for_senate_position2 or politician.running_for_representative):
            # Update the politician's record in the database to indicate primary participation
            politician.running_for_governor = True
            db.session.commit()

            # Render the template with the updated politician data
            state = State.query.first()
            return render_template('state.html', politician=politician, state=state)

    # Redirect to the home page if the form submission is invalid
    return redirect('/')


@app.route('/join_primary/senate1', methods=['POST'])
def join_primary_senate1():
    if request.method == 'POST':
        # Retrieve the logged-in politician based on the session username
        politician = Politician.query.filter_by(name=session['username']).first()

        # Check if the politician is already running for any position
        if politician and not (politician.running_for_governor or politician.running_for_senate_position1 or politician.running_for_senate_position2 or politician.running_for_representative):
            # Update the politician's record in the database to indicate primary participation
            politician.running_for_senate_position1 = True
            db.session.commit()

            # Render the template with the updated politician data
            state = State.query.first()
            return render_template('state.html', politician=politician, state=state)

    # Redirect to the home page if the form submission is invalid
    return redirect('/')


@app.route('/join_primary/senate2', methods=['POST'])
def join_primary_senate2():
    if request.method == 'POST':
        # Retrieve the logged-in politician based on the session username
        politician = Politician.query.filter_by(name=session['username']).first()

        # Check if the politician is already running for any position
        if politician and not (politician.running_for_governor or politician.running_for_senate_position1 or politician.running_for_senate_position2 or politician.running_for_representative):
            # Update the politician's record in the database to indicate primary participation
            politician.running_for_senate_position2 = True
            db.session.commit()

            # Render the template with the updated politician data
            state = State.query.first()
            return render_template('state.html', politician=politician, state=state)

    # Redirect to the home page if the form submission is invalid
    return redirect('/')


@app.route('/join_primary/representative', methods=['POST'])
def join_primary_representative():
    if request.method == 'POST':
        # Retrieve the logged-in politician based on the session username
        politician = Politician.query.filter_by(name=session['username']).first()

        # Check if the politician is already running for any position
        if politician and not (politician.running_for_governor or politician.running_for_senate_position1 or politician.running_for_senate_position2 or politician.running_for_representative):
            # Update the politician's record in the database to indicate primary participation
            politician.running_for_representative = True
            db.session.commit()

            # Render the template with the updated politician data
            state = State.query.first()
            return render_template('state.html', politician=politician, state=state)

    # Redirect to the home page if the form submission is invalid
    return redirect('/')

def login():
    if request.method == 'POST':
        username = request.form['name']
        password = request.form['id']

        # You can implement your own login logic here
        # For simplicity, let's assume the login is successful
        session['username'] = username

        # Redirect to the home page after successful login
        return redirect('/')

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the session data to log out the user
    session.clear()
    return redirect('/')


@app.template_global()
def getCookie(cookie_name):
	return request.cookies.get(cookie_name)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
