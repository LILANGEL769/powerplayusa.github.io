from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for, current_app, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from flask_migrate import Migrate
from sqlalchemy import UniqueConstraint, and_
from apscheduler.schedulers.background import BackgroundScheduler
import random
import geojson
import json
from sqlalchemy import or_

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///politicians.db'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.secret_key = 'BARRACKHUSSEINOBAMANOCAPONAFATSTACK'
db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Add this line
app.app_context().push()

def get_current_politician():
    # Your logic to retrieve the currently logged-in politician.
    # This is just a placeholder; you'd replace it with your actual logic.
    return Politician.query.get(session['politician_id'])

def get_current_year():
    import datetime

    # Define the start date
    start_date = datetime.datetime(1960, 1, 1)

    # Get the current date
    current_date = datetime.datetime.now()

    # Calculate the difference in minutes between the current date and the start date
    difference = (current_date - start_date).total_seconds() / 60

    # Calculate the current election year
    # Since 1 election year = 2 real-life minutes, divide the difference by 2
    current_year = 1960 + int(difference / 2)

    return current_year

def get_polling_data(state, candidates):
    polling_data = {}

    for candidate in candidates:
        # Get the poll_percent for this candidate in this state
        poll_percent = candidate.poll_percent  # Replace with actual method to get poll_percent

        polling_data[candidate.name] = poll_percent

    return polling_data

def redistribute_poll_percentages(politicians):
    total_poll_percent = sum([politician['poll_percent'] for politician in politicians])

    for politician in politicians:
        politician['poll_percent'] = (politician['poll_percent'] / total_poll_percent) * 100

    db.session.commit()

def add_states():
    # Create new state objects
    california = State(
        id=1,  # Set the ID manually
        name='California',
        population=39538223,
        social_stance='Progressive',
        economic_stance='Mixed',
        governor_salary=210000,
        senator_salary=174000,
        lt_governor_salary=151127,
        representative_salary=174000,
        ranked_choice_voting=False,
        term_limit=None,
        governor_id=14,
        lt_governor_id=15,
        senator1_id=16,
        senator2_id=17,
        representative_id=13
    )

    new_york = State(
        id=2,  # Set the ID manually
        name='New York',
        population=19530351,
        social_stance='Liberal',
        economic_stance='Mixed',
        governor_salary=225000,
        senator_salary=174000,
        lt_governor_salary=151500,
        representative_salary=174000,
        ranked_choice_voting=False,
        term_limit=None,
        governor_id=18,
        lt_governor_id=19,
        senator1_id=20,
        senator2_id=21,
        representative_id=22
    )

    # Add the state objects to the session
    db.session.add(california)
    db.session.add(new_york)

    # Commit the session to save the changes
    db.session.commit()

def transition_to_general():
    # Pause the primary job
    scheduler.pause_job('primary_job')

    with app.app_context():
        try:
            # Get all the primary elections
            primaries = Primary.query.all()

            # Get all unique states and positions from the primaries
            unique_states_and_positions = set([(primary.state_id, primary.position) for primary in primaries if primary.state_id is not None])

            for state_id, position in unique_states_and_positions:
                # Log the state_id
                current_app.logger.info(f"State ID: {state_id}, Position: {position}")

                with db.session.no_autoflush:
                    # Check if there are any candidates running for this position
                    primaries_for_position = Primary.query.filter_by(state_id=state_id, position=position).all()

                    if not primaries_for_position:  # No candidates running
                        state = State.query.get(state_id)
                        setattr(state, f'{position}_id', None)
                        current_app.logger.info(f"No candidates for position {position} in state {state_id}. Setting owner to None.")
                        db.session.commit()
                        continue

                    parties = ['States Rights Party', 'Bull Moose Party', 'Libertarian', 'Socialist']  # Add other parties as needed
                    for party in parties:
                        winner_primary = Primary.query.join(
                            Politician, Primary.politician_id == Politician.id
                        ).filter(
                            Primary.state_id == state_id,
                            Primary.position == position,
                            Politician.party == party  # Only consider candidates of this party
                        ).order_by(Primary.poll_percent.desc()).first()

                        if winner_primary is not None:  # A candidate from this party exists
                            winner = Politician.query.filter_by(id=winner_primary.politician_id).first()

                            # Check if winner is None
                            if winner is None:
                                # If winner is None, skip this iteration of the loop and continue with the next one
                                current_app.logger.info(f"Skipping state {state_id} for party {party} because no winner was found")
                                continue

                            # Reset the rallies_run and ads_run values for the winner
                            winner.rallies_run = 0
                            winner.ads_run = 0

                            # Log the winner's id, name, and poll_percent
                            current_app.logger.info(f"Winner of primary in state {state_id} for party {party}: {winner.id}, {winner.name}, {winner_primary.poll_percent}")

                            # Log the values of state_id and winner.id before creating a GeneralElection record
                            current_app.logger.info(f"Creating GeneralElection record with state_id = {state_id}, politician_id = {winner.id}")

                            # Create a new general election with the winner
                            general_election = GeneralElection(state_id=state_id, position=position, politician_id=winner.id)
                            general_election.poll_percent = 0.001  # Set initial poll_percent to a small constant
                            db.session.add(general_election)

            # Delete all primary elections
            for primary in primaries:
                db.session.delete(primary)

            # Commit the changes to the database
            db.session.commit()

            # After handling the primaries, deal with finished general elections
            finished_generals = GeneralElection.query.filter_by(is_ongoing=False).all()

            for general in finished_generals:
                current_app.logger.info(f"Deleting finished general election {general.id}")
                db.session.delete(general)

            # Commit the changes to the database
            db.session.commit()

            return {'message': 'Transitioned to general elections and cleared finished ones'}

        except Exception as e:
            current_app.logger.error(f"Error occurred: {e}")
            db.session.rollback()

            return {'message': 'An error occurred during the transition.', 'error': str(e)}

def end_general_elections():
    with app.app_context():
        try:
            # Get all the ongoing general elections
            general_elections = GeneralElection.query.filter_by(is_ongoing=True).all()

            # Get all unique states and positions from the general elections
            unique_states_and_positions = set([(general_election.state_id, general_election.position) for general_election in general_elections if general_election.state_id is not None])

            for state_id, position in unique_states_and_positions:
                # Find the winner of the general election
                winner_general_election = GeneralElection.query.filter_by(state_id=state_id, position=position, is_ongoing=True).order_by(GeneralElection.poll_percent.desc()).first()

                if winner_general_election is not None:  # A candidate exists
                    winner = Politician.query.filter_by(id=winner_general_election.politician_id).first()

                    # Check if winner is None
                    if winner is None:
                        # If winner is None, skip this iteration of the loop and continue with the next one
                        current_app.logger.info(f"Skipping state {state_id} for position {position} because no winner was found")
                        continue

                    # Reset the rallies_run and ads_run values for the winner
                    winner.rallies_run = 0
                    winner.ads_run = 0

                    # Update the state with the id of the winning politician
                    state = State.query.get(state_id)
                    setattr(state, f'{position}_id', winner.id)

                    # Log the winner's id, name, and poll_percent
                    current_app.logger.info(f"Winner of general election in state {state_id} for position {position}: {winner.id}, {winner.name}, {winner_general_election.poll_percent}")

                    # Update winner's money based on position
                    if position == "governor":
                        winner.money += winner.state.governor_salary
                    elif position == "senator":
                        winner.money += winner.state.senator_salary
                    elif position == "lt_governor":
                        winner.money += winner.state.lt_governor_salary
                    elif position == "representative":
                        winner.money += winner.state.representative_salary
                    else:
                        current_app.logger.error(f"Unknown position: {position}")

                # Delete all general elections for this state and position
                all_general_elections = GeneralElection.query.filter_by(state_id=state_id, position=position, is_ongoing=True).all()
                for general_election in all_general_elections:
                    db.session.delete(general_election)
                    db.session.flush()  # Force the session to update the transaction

            # Commit the changes to the database
            db.session.commit()

            # Set up new primaries 
            setup_new_primaries()

        except Exception as e:
            current_app.logger.error(f"Error occurred: {e}")
            db.session.rollback()

    return {'message': 'Ended general elections and set up new primaries'}

def setup_new_primaries():
    with app.app_context():
        try:
            # Get all the general elections that are not ongoing
            general_elections = GeneralElection.query.filter_by(is_ongoing=False).all()

            for general_election in general_elections:
                # Set the general election to ongoing
                general_election.is_ongoing = True

            # Get all politicians
            politicians = Politician.query.all()

            # Set up new primary for each politician
            for politician in politicians:
                new_primary = Primary(position=politician.position, politician_id=politician.id, state_id=politician.state_id)
                new_primary.poll_percent = 0.001  # Set initial poll_percent to a small constant
                db.session.add(new_primary)

            # Commit the changes to the database
            db.session.commit()

        except Exception as e:
            current_app.logger.error(f"Error occurred: {e}")
            db.session.rollback()

    # Resume the primary job
    scheduler.resume_job('primary_job')

class Politician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    party = db.Column(db.String(100))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(100))
    state_id = db.Column(db.Integer, db.ForeignKey('state.id'))
    money = db.Column(db.Integer, default=1000000)
    hourly_money_generation = db.Column(db.Integer, default=10000)
    fundraiser_cost = db.Column(db.Integer, default=5)  # New field
    total_poll_percent = db.Column(db.Float, nullable=False, default=100.0)
    rallies_run = db.Column(db.Integer, default=0)
    ads_run = db.Column(db.Integer, default=0)

    state = db.relationship('State', backref=db.backref('politicians', lazy=True), foreign_keys=[state_id])

    def __init__(self, name, gender, party, bio, avatar, state_id):
        self.name = name
        self.gender = gender
        self.party = party
        self.bio = bio
        self.avatar = avatar
        self.state_id = state_id
        self.money = 1000000
        self.hourly_money_generation = 10000
        self.fundraiser_cost = 5  # Initial cost for holding a fundraiser

def increment_money():
    with app.app_context():
        politicians = Politician.query.all()
        for politician in politicians:
            politician.money += politician.hourly_money_generation  # Adjust this line
        db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=increment_money, trigger="interval", seconds=60)  # Changed to 1 hour
scheduler.add_job(func=transition_to_general, trigger="interval", minutes=5, id='primary_job')
scheduler.add_job(func=end_general_elections, trigger="interval", minutes=10)
scheduler.start()

class Primary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.String(100))
    politician_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    state_id = db.Column(db.Integer, db.ForeignKey('state.id'), nullable=False)
    poll_percent = db.Column(db.Float, default=0)  # New field
    rallies_run = db.Column(db.Integer, default=0)
    ads_run = db.Column(db.Integer, default=0)

    def __init__(self, position, politician_id, state_id):
        self.position = position
        self.politician_id = politician_id
        self.state_id = state_id
        self.poll_percent = 0  # Set initial poll_percent to 0

class GeneralElection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    state_id = db.Column(db.Integer, db.ForeignKey('state.id'), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    politician_id = db.Column(db.Integer, db.ForeignKey('politician.id'), nullable=False)
    is_ongoing = db.Column(db.Boolean, default=True)
    poll_percent = db.Column(db.Float, default=0)  # Add this line
    rallies_run = db.Column(db.Integer, default=0)
    ads_run = db.Column(db.Integer, default=0)

    def __init__(self, position, politician_id, state_id):
        self.position = position
        self.politician_id = politician_id
        self.state_id = state_id
        self.poll_percent = 0  # Set initial poll_percent to 0

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
    
    # New columns
    governor_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    lt_governor_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    senator1_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    senator2_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    representative_id = db.Column(db.Integer, db.ForeignKey('politician.id'))

    # New relationships
    governor = db.relationship('Politician', foreign_keys=[governor_id], uselist=False)
    lt_governor = db.relationship('Politician', foreign_keys=[lt_governor_id], uselist=False)
    senator1 = db.relationship('Politician', foreign_keys=[senator1_id], uselist=False)
    senator2 = db.relationship('Politician', foreign_keys=[senator2_id], uselist=False)
    representative = db.relationship('Politician', foreign_keys=[representative_id], uselist=False)

    def __init__(self, name, population, social_stance, economic_stance, governor_salary,
                 senator_salary, lt_governor_salary, representative_salary, 
                 ranked_choice_voting, term_limit, governor_id=None, lt_governor_id=None, 
                 senator1_id=None, senator2_id=None, representative_id=None):
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
        self.governor_id = governor_id
        self.lt_governor_id = lt_governor_id
        self.senator1_id = senator1_id
        self.senator2_id = senator2_id
        self.representative_id = representative_id

class OvalOffice(db.Model):
    __tablename__ = 'OvalOffice'
    
    id = db.Column(db.Integer, primary_key=True)
    president_id = db.Column(db.Integer, db.ForeignKey('politician.id'), nullable=False)
    vice_president_id = db.Column(db.Integer, db.ForeignKey('politician.id'), nullable=False)
    term_start = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    president = db.relationship('Politician', foreign_keys=[president_id])
    vice_president = db.relationship('Politician', foreign_keys=[vice_president_id])

class PresidentialPrimary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    politician_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    poll_percent = db.Column(db.Float, default=0.0)
    rallies_run = db.Column(db.Integer, default=0)
    ads_run = db.Column(db.Integer, default=0)
    position = db.Column(db.String(100))

    politician = db.relationship('Politician', backref='presidential_primaries')

    def __init__(self, position, year, politician_id):
        self.year = year
        self.politician_id = politician_id
        self.poll_percent = 0  # Set initial poll_percent to 0

class PresidentialGeneralElection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    politician_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    is_ongoing = db.Column(db.Boolean, default=True)
    poll_percent = db.Column(db.Float, default=0.0)
    rallies_run = db.Column(db.Integer, default=0)
    ads_run = db.Column(db.Integer, default=0)
    position = db.Column(db.String(100))

    def __init__(self, position, year, politician_id):
        self.year = year
        self.politician_id = politician_id
        self.poll_percent = 0  # Set initial poll_percent to 0

class County(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    state_id = db.Column(db.Integer, db.ForeignKey('state.id'))
    population = db.Column(db.Integer)  # Optional field

    # Backrefs for relationships
    state = db.relationship('State', backref=db.backref('counties', lazy=True))
    polling = db.relationship('CountyPolling', backref='county', lazy=True)


class CountyPolling(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    county_id = db.Column(db.Integer, db.ForeignKey('county.id'))
    politician_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    poll_percent = db.Column(db.Float)

    # Backrefs for relationships
    politician = db.relationship('Politician', backref=db.backref('county_polling', lazy=True))

class Party(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    chair_id = db.Column(db.Integer, db.ForeignKey('politician.id'), nullable=True)
    vice_chair_id = db.Column(db.Integer, db.ForeignKey('politician.id'), nullable=True)
    treasurer_id = db.Column(db.Integer, db.ForeignKey('politician.id'), nullable=True)
    
    # Relationships for chair, vice-chair, and treasurer
    chair = db.relationship('Politician', foreign_keys=[chair_id])
    vice_chair = db.relationship('Politician', foreign_keys=[vice_chair_id])
    treasurer = db.relationship('Politician', foreign_keys=[treasurer_id])
    money = db.Column(db.Float, default=5000000.0)

class PartyTransaction(db.Model):
    __tablename__ = 'party_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'))
    sender_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    amount = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    party = db.relationship('Party')
    sender = db.relationship('Politician', foreign_keys=[sender_id])
    recipient = db.relationship('Politician', foreign_keys=[recipient_id])

class PartyElectionNomination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    politician_id = db.Column(db.Integer, db.ForeignKey('politician.id'))
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'))  # Added this line
    position = db.Column(db.String(50))  # 'chair', 'vice_chair', or 'treasurer'
    votes = db.Column(db.Integer, default=0)

    def vote(self):
        self.votes += 1
        db.session.commit()

def initialize_parties():
    # Check if the Bull Moose Party exists
    if not Party.query.filter_by(name="Bull Moose Party").first():
        bull_moose_party = Party(name="Bull Moose Party")
        db.session.add(bull_moose_party)

    # Check if the Vanguard Party exists
    if not Party.query.filter_by(name="Vanguard Party").first():
        vanguard_party = Party(name="Vanguard Party")
        db.session.add(vanguard_party)

    # Check if the States Rights Party exists
    if not Party.query.filter_by(name="States Rights Party").first():
        states_rights_party = Party(name="States Rights Party")
        db.session.add(states_rights_party)

    # Commit the changes to the database
    db.session.commit()

# Call the function to initialize the parties
initialize_parties()

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
        state_id = request.form['state_id']

        filename = secure_filename(avatar.filename)
        avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        politician = Politician(name=name, gender=gender, party=party, bio=bio, avatar=filename, state_id=state_id)
        db.session.add(politician)
        db.session.commit()
        return redirect(f'/profile/{politician.id}')

    # Query all states from the database
    states = State.query.all()
    return render_template('create_politician.html', states=states)

@app.route('/signup', methods=['POST'])
def signup():
    # Assume user_id is the id of the currently logged-in user
    user_id = session['politician_id']
    position = request.form.get('position')
    primary_state_id = request.form.get('state_id')  # Get the state_id from the form data

    # Fetch the user's profile information
    politician = Politician.query.get(user_id)
    if politician is None:
        return jsonify({'error': 'Politician not found.'}), 400

    # Fetch the state_id from the user's profile
    politician_state_id = politician.state_id

    # Check if the state_id of the primary matches the state_id of the user's profile
    if str(politician_state_id) != primary_state_id:
        return jsonify({'error': 'You can only register for a primary in your selected state.'}), 400

    # Check if the user is already registered for a primary in their state
    existing_primary = Primary.query.filter_by(politician_id=user_id, state_id=politician_state_id).first()
    if existing_primary is not None:
        return jsonify({'error': 'You are already registered for a primary in your state.'}), 400

    # If the user isn't already registered for a primary in their state,
    # register them for the primary in their state
    primary = Primary(position=position, politician_id=user_id, state_id=politician_state_id)
    db.session.add(primary)
    db.session.commit()

    return jsonify({'message': 'Successfully registered for primary.'}), 200

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if request.method == 'POST':
        if 'politician_id' in session:
            politician_id = session['politician_id']

            # Check if politician is signed up for a primary
            existing_primary = Primary.query.filter_by(politician_id=politician_id).first()
            if not existing_primary:
                return jsonify(error="You are not signed up for a primary."), 400

            # Remove the politician from the primary
            db.session.delete(existing_primary)
            db.session.commit()

            return jsonify(success="Successfully withdrew from primary.")
        else:
            return jsonify(error="You are not logged in."), 400
    else:
        return redirect(url_for('index'))

@app.template_global()
def get_state_name(state_id):
    state = State.query.get(state_id)
    if state:
        return state.name
    return 'Unknown'

@app.route('/profile/<int:politician_id>')
def profile(politician_id):
    politician = Politician.query.get(politician_id)
    print("Profile ID:", politician.id)  # Log the profile's politician_id

    return render_template('profile.html', politician=politician, get_state_name=get_state_name)

def get_state_data(state_id):
    # Get the state from the database
    state = State.query.get(state_id)
    
    # If no state was found, return None
    if state is None:
        return None

    # Fetch the politicians from the database based on the IDs
    governor = Politician.query.get(state.governor_id)
    lt_governor = Politician.query.get(state.lt_governor_id)
    senator1 = Politician.query.get(state.senator1_id)
    senator2 = Politician.query.get(state.senator2_id)
    representative = Politician.query.get(state.representative_id)

    # Construct the state data
    state_data = {
        'name': state.name,
        'population': state.population,
        'social_stance': state.social_stance,
        'economic_stance': state.economic_stance,
        'governor_salary': state.governor_salary,
        'senator_salary': state.senator_salary,
        'lt_governor_salary': state.lt_governor_salary,
        'representative_salary': state.representative_salary,
        'ranked_choice_voting': state.ranked_choice_voting,
        'term_limit': state.term_limit,
        'governor': {
            'id': state.governor_id,
            'username': governor.name if governor else None,
        },
        'lt_governor': {
            'id': state.lt_governor_id,
            'username': lt_governor.name if lt_governor else None,
        },
        'senator1': {
            'id': state.senator1_id,
            'username': senator1.name if senator1 else None,
        },
        'senator2': {
            'id': state.senator2_id,
            'username': senator2.name if senator2 else None,
        },
        'representative': {
            'id': state.representative_id,
            'username': representative.name if representative else None,
        },
    }

    return state_data

# Define the state route
@app.route('/state/<int:state_id>')
def state(state_id):
    state_data = State.query.get(state_id)
    if state_data is None:
        abort(404)  # Sends a 404 error to the client

    # Retrieve the logged-in politician based on the session username
    if 'politician_id' in session:
        politician = Politician.query.get(session['politician_id'])
        user_is_signed_up = Primary.query.filter_by(politician_id=politician.id, state_id=state_id).first() is not None
    else:
        politician = None
        user_is_signed_up = False

    # Retrieve politicians related to the state
    state_data.governor = Politician.query.get(state_data.governor_id)
    state_data.lt_governor = Politician.query.get(state_data.lt_governor_id)
    state_data.senator1 = Politician.query.get(state_data.senator1_id)
    state_data.senator2 = Politician.query.get(state_data.senator2_id)
    state_data.representative = Politician.query.get(state_data.representative_id)

    # Generate the primaries dictionary
    primaries = {}
    positions = ['governor', 'lt_governor', 'senator1', 'senator2', 'representative']
    for position in positions:
        # Query the Primary table to get all politicians running for this position
        primaries_for_position = Primary.query.filter_by(position=position, state_id=state_id).all()

        # For each primary, get the corresponding Politician object and add it to the list
        politicians_for_position = [{'politician': Politician.query.get(primary.politician_id), 'poll_percent': primary.poll_percent} for primary in primaries_for_position]

        # Add the list of Politician objects to the primaries dictionary
        primaries[position] = politicians_for_position

    # Generate the general elections dictionary
    general_elections = {}
    for position in positions:
        # Query the GeneralElection table to get all politicians running for this position
        general_elections_for_position = GeneralElection.query.filter_by(position=position, state_id=state_id).all()

        # For each general election, get the corresponding Politician object and add it to the list
        politicians_for_position = [{'politician': Politician.query.get(general_election.politician_id)} for general_election in general_elections_for_position]

        # Add the list of Politician objects to the general elections dictionary
        general_elections[position] = politicians_for_position

    user_in_general = False
    if politician:
        for position, politicians in general_elections.items():
            if any(p['politician'].id == politician.id for p in politicians):
                user_in_general = True
                break

    return render_template('state.html', state=state_data, politician=politician,
                           user_is_signed_up=user_is_signed_up, primaries=primaries,
                           general_elections=general_elections, user_in_general=user_in_general)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['name']
        password = request.form['id']

        # Assuming the 'password' is actually the politician's id
        # You might want to change this to actual password validation logic in a real app
        session['politician_id'] = password  # Store politician's id in the session

        # Redirect to the home page after successful login
        return redirect('/')

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the session data to log out the user
    session.clear()
    return redirect('/')

from flask import render_template_string

@app.route('/polling', methods=['GET'])
def polling():
    states = State.query.all()
    primaries = PresidentialPrimary.query.all()

    # Check if a politician is logged in
    politician_id = session.get('politician_id', None)

    # Calculate the current year
    import datetime
    start_date = datetime.datetime(1960, 1, 1)
    current_date = datetime.datetime.now()
    difference = (current_date - start_date).total_seconds() / 60
    current_year = 1960 + int(difference / 2)

    # Check if the logged in politician is registered for the current primary
    if politician_id:
        registered_primary = PresidentialPrimary.query.filter_by(politician_id=politician_id, year=current_year).first()
    else:
        registered_primary = None

    # Fetch all bmp and srp candidates
    bmp_candidates = [(primary.politician.name, primary.poll_percent) for primary in primaries if primary.politician.party == 'Bull Moose Party']
    srp_candidates = [(primary.politician.name, primary.poll_percent) for primary in primaries if primary.politician.party == 'States Rights Party']

    state_data = {}
    for state in states:
        state_data[state.name] = {
            'name': state.name,
            'economic_stance': state.economic_stance,
            'social_stance': state.social_stance,
            'polling': {primary.politician.name: primary.poll_percent for primary in primaries}
        }

    # Print the state data
    print(state_data)

    return render_template('polling.html', states=states, state_data=state_data, bmp_candidates=bmp_candidates, srp_candidates=srp_candidates, registered=registered_primary is not None)

@app.route('/register_presidential_candidate', methods=['POST'])
def register_presidential_candidate():
    if 'politician_id' not in session:
        # If the user is not logged in, redirect them to the login page
        return redirect(url_for('login'))

    # Get the logged in politician's id from the session
    politician_id = session['politician_id']

    # Fetch the politician from the database using the id
    politician = Politician.query.get(politician_id)

    # If politician doesn't exist, handle appropriately (maybe redirect to an error page or login page)
    if politician is None:
        return redirect(url_for('login'))

    import datetime

    # Define the start date
    start_date = datetime.datetime(1960, 1, 1)

    # Get the current date
    current_date = datetime.datetime.now()

    # Calculate the difference in minutes between the current date and the start date
    difference = (current_date - start_date).total_seconds() / 60

    # Calculate the current election year
    # Since 1 election year = 2 real-life minutes, divide the difference by 2
    current_year = 1960 + int(difference / 2)

    # Check if a primary already exists for the current year and the logged-in politician
    existing_primary = PresidentialPrimary.query.filter_by(year=current_year, politician_id=politician.id).first()
    if existing_primary:
        # Primary already exists, redirect to the polling page
        return redirect(url_for('polling'))

    # Create a new PresidentialPrimary object
    primary = PresidentialPrimary(position='President', year=current_year, politician_id=politician.id)

    # Add the new primary to the database
    db.session.add(primary)
    db.session.commit()

    return redirect(url_for('polling'))

@app.route('/withdraw_presidential_candidate', methods=['POST'])
def withdraw_presidential_candidate():
    if 'politician_id' not in session:
        # If the user is not logged in, redirect them to the login page
        return redirect(url_for('login'))

    # Fetch the politician by ID
    politician = Politician.query.get(session['politician_id'])

    # Check if the politician exists
    if politician:
        # Define the current year
        current_year = get_current_year()

        # Check if a primary exists for the current year and the logged-in politician
        existing_primary = PresidentialPrimary.query.filter_by(year=current_year, politician_id=politician.id).first()
        if existing_primary:
            # Primary exists, delete it
            db.session.delete(existing_primary)
            db.session.commit()

        return redirect(url_for('polling'))
    else:
        # Politician not found, return an error or handle it appropriately
        return "Politician not found", 404

@app.route('/electionstate/<int:state_id>')
def electionstate(state_id):
    state = get_state_data(state_id)
    if state is None:
        return "State not found", 404

    primaries = {}
    general_elections = {}
    positions = ['governor', 'lt_governor', 'senator1', 'senator2', 'representative']
    parties = ['States Rights Party', 'Bull Moose Party', 'Libertarian', 'Socialist']  # Update party names

    for position in positions:
        primaries_for_position_by_party = {}
        for party in parties:
            primaries_for_position = Primary.query.join(
                Politician, Primary.politician_id == Politician.id
            ).filter(
                Primary.position == position,
                Primary.state_id == state_id,
                Politician.party == party  # Only consider candidates of this party
            ).all()
            
            politicians_for_position = []
            for primary in primaries_for_position:
                politician = Politician.query.get(primary.politician_id)
                if politician is not None:
                    poll_percent = primary.poll_percent if primary.poll_percent is not None else 0
                    politicians_for_position.append({'politician': politician, 'poll_percent': poll_percent})

            total_poll_percent = sum([politician['poll_percent'] for politician in politicians_for_position])
            if total_poll_percent == 0:
                for politician in politicians_for_position:
                    politician['poll_percent'] = 100.0 / len(politicians_for_position)
            else:
                for politician in politicians_for_position:
                    politician['poll_percent'] = (politician['poll_percent'] / total_poll_percent)

            primaries_for_position_by_party[party] = politicians_for_position

        primaries[position] = primaries_for_position_by_party

        general_elections_for_position = GeneralElection.query.filter_by(position=position, state_id=state_id, is_ongoing=True).all()
        politicians_for_position = [{'politician': Politician.query.get(general_election.politician_id), 'poll_percent': general_election.poll_percent} for general_election in general_elections_for_position]

        total_poll_percent = sum([politician['poll_percent'] for politician in politicians_for_position])
        if total_poll_percent == 0:
            for politician in politicians_for_position:
                politician['poll_percent'] = 100.0 / len(politicians_for_position)
        else:
            for politician in politicians_for_position:
                politician['poll_percent'] = (politician['poll_percent'] / total_poll_percent)

        general_elections[position] = politicians_for_position

    return render_template('electionstate.html', state=state, primaries=primaries, general_elections=general_elections)

@app.route('/rally/<int:politician_id>', methods=['GET', 'POST'])
def rally(politician_id):
    politician = Politician.query.get(politician_id)

    # Check if politician is in a general election
    general = GeneralElection.query.filter_by(politician_id=politician.id, is_ongoing=True).first()
    if general:
        if politician.money < 80000:
            flash('You do not have enough funds to hold a rally.')
            return redirect(url_for('state', state_id=politician.state_id))

        politician.money -= 80000
        general.rallies_run += 1

        # Calculate the rally boost
        rally_boost = random.uniform(0.005, 0.015)
        
        # Print the poll_percent before the update
        print(f"Before rally: {general.poll_percent}")

        general.poll_percent += rally_boost / 100

        # Print the poll_percent after the update
        print(f"After rally: {general.poll_percent}")

        # Distribute the decrease among the other politicians
        others = GeneralElection.query.filter(and_(GeneralElection.state_id == general.state_id, GeneralElection.position == general.position, GeneralElection.politician_id != politician.id)).all()
        total = sum([other.poll_percent for other in others])
        for other in others:
            if total != 0:
                decrease = min((other.poll_percent / total) * rally_boost, other.poll_percent)
                other.poll_percent -= decrease

        db.session.commit()
        flash('You have held a successful rally.')
        return redirect(url_for('state', state_id=politician.state_id))

    # The politician is not in a general election, so handle the primary election scenario
    primary = Primary.query.filter_by(politician_id=politician.id).first()
    if politician.money < 80000:
        flash('You do not have enough funds to hold a rally.')
        return redirect(url_for('state', state_id=politician.state_id))

    politician.money -= 80000
    primary.rallies_run += 1

    # Calculate the rally boost
    rally_boost = random.uniform(0.005, 0.015)
    
    # Print the poll_percent before the update
    print(f"Before rally: {primary.poll_percent}")

    primary.poll_percent += rally_boost

    # Print the poll_percent after the update
    print(f"After rally: {primary.poll_percent}")

    # Distribute the decrease among the other politicians
    others = Primary.query.filter(and_(Primary.state_id == primary.state_id, Primary.position == primary.position, Primary.politician_id != politician.id)).all()
    total = sum([other.poll_percent for other in others])
    for other in others:
        if total != 0:
            decrease = min((other.poll_percent / total) * rally_boost, other.poll_percent)
            other.poll_percent -= decrease

    db.session.commit()
    flash('You have held a successful rally.')
    return redirect(url_for('state', state_id=politician.state_id))

@app.route('/ads/<int:politician_id>', methods=['GET', 'POST'])
def ads(politician_id):
    politician = Politician.query.get(politician_id)

    # Check if politician is in a general election
    general = GeneralElection.query.filter_by(politician_id=politician.id, is_ongoing=True).first()
    if general:
        if politician.money < 120000:
            flash('You do not have enough funds to run ads.')
            return redirect(url_for('state', state_id=politician.state_id))
        
        politician.money -= 120000
        general.ads_run += 1

        # Calculate the ad boost
        ad_boost = random.uniform(0.015, 0.02)
        
        # Print the poll_percent before the update
        print(f"Before ad: {general.poll_percent}")

        general.poll_percent += ad_boost / 100

        # Print the poll_percent after the update
        print(f"After ad: {general.poll_percent}")

        # Distribute the decrease among the other politicians
        others = GeneralElection.query.filter(and_(GeneralElection.state_id == general.state_id, GeneralElection.position == general.position, GeneralElection.politician_id != politician.id)).all()
        total = sum([other.poll_percent for other in others])
        for other in others:
            if total != 0:
                decrease = min((other.poll_percent / total) * ad_boost, other.poll_percent)
                other.poll_percent -= decrease

        db.session.commit()
        flash('Your ads have been successful.')
        return redirect(url_for('state', state_id=politician.state_id))

    # The politician is not in a general election, so handle the primary election scenario
    primary = Primary.query.filter_by(politician_id=politician.id).first()
    if politician.money < 120000:
        flash('You do not have enough funds to run ads.')
        return redirect(url_for('state', state_id=politician.state_id))
    
    politician.money -= 120000
    primary.ads_run += 1

    # Calculate the ad boost
    ad_boost = random.uniform(0.015, 0.02)
    
    # Print the poll_percent before the update
    print(f"Before ad: {primary.poll_percent}")

    primary.poll_percent += ad_boost

    # Print the poll_percent after the update
    print(f"After ad: {primary.poll_percent}")

    # Distribute the decrease among the other politicians
    others = Primary.query.filter(and_(Primary.state_id == primary.state_id, Primary.position == primary.position, Primary.politician_id != politician.id)).all()
    total = sum([other.poll_percent for other in others])
    for other in others:
        if total != 0:
            decrease = min((other.poll_percent / total) * ad_boost, other.poll_percent)
            other.poll_percent -= decrease

    db.session.commit()
    flash('Your ads have been successful.')
    return redirect(url_for('state', state_id=politician.state_id))

@app.route('/transition_to_general', methods=['POST'])
def transition_to_general():
    # Get all the primary elections
    primaries = Primary.query.all()

    for primary in primaries:
        # Find the winner of each primary
        winner = db.session.query(Politician).join(Primary).filter(Primary.id == primary.id).order_by(Politician.popularity.desc()).first()
        
        # Create a new general election with the winner
        general_election = GeneralElection(state_id=primary.state_id, position=primary.position, politician_id=winner.id)
        db.session.add(general_election)

        # Delete the primary election
        db.session.delete(primary)

    # Commit the changes to the database
    db.session.commit()

    return jsonify({'message': 'Transitioned to general elections'})

@app.route('/oval_office')
def oval_office():
    all_offices = OvalOffice.query.all()
    print(f"All offices: {all_offices}")
    current_office = OvalOffice.query.order_by(OvalOffice.term_start.desc()).first()
    print(f"Current office: {current_office}")
    if current_office is None:
        return "No current office found"
    president = Politician.query.get(current_office.president_id)
    vice_president = Politician.query.get(current_office.vice_president_id)
    return render_template('oval_office.html', president=president, vice_president=vice_president)

@app.route('/party/<int:party_id>', methods=['GET'])
def party_details(party_id):
    # Fetch the specified party details from the database using the party ID
    party = Party.query.get(party_id)
    # If the party doesn't exist, return a 404 error
    if not party:
        return "Party not found", 404

    current_politician = get_current_politician()

    # Fetch transactions related to the party
    transactions = PartyTransaction.query.filter(or_(PartyTransaction.sender_id == party.id, PartyTransaction.recipient_id == party.id)).all()

    # Fetch nominations for leadership positions
    nominations = PartyElectionNomination.query.filter_by(party_id=party.id).all()

    # Render the party.html template with the party's details, the related transactions, and the nominations
    return render_template('party.html', party=party, current_politician=current_politician, transactions=transactions, nominations=nominations)

@app.route('/make_transaction', methods=['POST'])
def make_transaction():
    # Get the currently logged-in politician's ID from the Flask session
    current_politician_id = session.get('politician_id')
    if not current_politician_id:
        return jsonify({'message': 'Error: No politician is currently logged in'}), 400

    # Fetch the current_politician object using the ID
    current_politician = Politician.query.get(current_politician_id)
    if not current_politician:
        return jsonify({'message': f'Error: The logged-in politician with ID {current_politician_id} was not found in the database'}), 400
    
    amount = float(request.form.get('amount'))
    recipient_name = request.form.get('recipient')
    
    # Fetch the party based on the current logged-in politician's party name
    party = Party.query.filter_by(name=current_politician.party).first()
    if not party:
        return jsonify({'message': f'Error: The party "{current_politician.party}" of the logged-in politician was not found'}), 400

    if party.money < amount:
        return jsonify({'message': f'Error: Insufficient party money. Only ${party.money:.2f} available, but ${amount:.2f} requested.'}), 400

    recipient = Politician.query.filter_by(name=recipient_name).first()
    if not recipient:
        return jsonify({'message': f'Error: Recipient "{recipient_name}" not found'}), 400

    # Update party money and recipient's money
    party.money -= amount
    recipient.money += amount

    # Log the transaction
    transaction = PartyTransaction(sender_id=current_politician.id, recipient_id=recipient.id, amount=amount)
    db.session.add(transaction)
    db.session.commit()

    return jsonify({'message': f'Successfully transferred ${amount:.2f} to {recipient_name}.'})

@app.route('/nominate', methods=['POST'])
def nominate():
    position = request.form.get('position')
    politician_id = session.get('politician_id')
    
    # Get the party of the logged-in politician
    politician = Politician.query.get(politician_id)
    if not politician:
        return jsonify({'message': 'Logged-in politician not found.'}), 400

    # Fetch the party by its name
    party = Party.query.filter_by(name=politician.party).first()
    if not party:
        return jsonify({'message': 'Party for the logged-in politician not found.'}), 400
    party_id = party.id
    
    existing_nomination = PartyElectionNomination.query.filter_by(politician_id=politician_id, position=position).first()
    if existing_nomination:
        return jsonify({'message': 'You have already nominated yourself for this position.'}), 400

    nomination = PartyElectionNomination(politician_id=politician_id, position=position, party_id=party_id)
    db.session.add(nomination)
    db.session.commit()
    
    return jsonify({'message': 'Successfully nominated.'})

@app.route('/vote/<int:nomination_id>', methods=['POST'])
def vote(nomination_id):
    nomination = PartyElectionNomination.query.get(nomination_id)
    if not nomination:
        return jsonify({'message': 'Nomination not found.'}), 404

    nomination.vote()
    return jsonify({'message': 'Vote counted.'})

@app.route('/withdraw_nomination/<int:nomination_id>', methods=['POST'])
def withdraw_nomination(nomination_id):
    # Get the nomination using the provided ID
    nomination = PartyElectionNomination.query.get(nomination_id)
    if not nomination:
        return jsonify({'message': 'Nomination not found.'}), 404

    # Ensure the logged-in user is the one who made the nomination
    politician_id = session.get('politician_id')
    if nomination.politician_id != politician_id:
        return jsonify({'message': 'Not authorized to withdraw this nomination.'}), 403

    # Delete the nomination
    db.session.delete(nomination)
    db.session.commit()

    return jsonify({'message': 'Successfully withdrawn from nomination.'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
