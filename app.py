from datetime import timedelta
from dotenv import load_dotenv
import os
from flask import Flask,redirect,session,url_for,request,render_template,flash
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO,send,emit,join_room
import random



load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=1)

google_auth_uri = os.getenv('GOOGLE_AUTH_URI')
google_client_id = os.getenv('GOOGLE_CLIENT_ID')
google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
redirect_uri = os.getenv('REDIRECT_URI')
token_uri = os.getenv('GOOGLE_TOKEN_URI')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL') or 'sqlite:///database/poll.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)

class questions(db.Model):
    poll_id = db.Column(db.INTEGER,primary_key=True)
    creator_id = db.Column(db.String(100))
    question = db.Column(db.String(1500))

    def __init__(self,poll_id,creator_id,question):
        self.poll_id = poll_id
        self.creator_id = creator_id
        self.question = question
        

class choices(db.Model):
    choice_id = db.Column(db.INTEGER,primary_key=True)
    poll_id = db.Column(db.INTEGER)
    choice = db.Column(db.String(100))
    vote = db.Column(db.INTEGER)

    def __init__(self,poll_id,choice,vote):
        self.poll_id = poll_id
        self.choice = choice
        self.vote = vote

class voters(db.Model):
    voter_id = db.Column(db.INTEGER,primary_key=True)
    poll_id = db.Column(db.INTEGER)
    voter_email = db.Column(db.String(100))
    voter_name = db.Column(db.String(100))

    def __init__(self,poll_id,voter_email,voter_name):
        self.poll_id = poll_id
        self.voter_email = voter_email
        self.voter_name = voter_name




# auth_uri = google_auth_uri + '?client_id={}&redirect_uri={}&response_type=code&scope=email'.format(google_client_id,redirect_uri)
# print(auth_uri)







@app.route('/login/')
def login():
    if 'credentials' in session:
        return redirect(url_for('home'))
    else:
        return render_template('login.html')



@app.route('/login/callback/')
def callback():
    if 'code' not in request.args:
        auth_uri = google_auth_uri + '?client_id={}&redirect_uri={}&response_type=code&scope=email profile'.format(google_client_id,redirect_uri)
        return redirect(auth_uri)
    else:
        auth_code = request.args.get('code')
        request_params = {
            'client_id': google_client_id,
            'client_secret': google_client_secret,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }
        resp = requests.post(token_uri,data=request_params).json()
        res = requests.get('https://www.googleapis.com/oauth2/v3/userinfo',params={'access_token': resp.get('access_token')}).json()
        session.permanent = True
        session['credentials'] = res
        return redirect(url_for('home'))

@app.route('/home/')
def home():
    if 'credentials' in session:
        credentials = session['credentials']
        return render_template('home.html',name=credentials.get('name'))
    else:
        return redirect(url_for('login'))


@app.route('/logout/')
def logout():
    session.pop('credentials',None)
    return redirect(url_for('home'))

@app.route('/createPoll/',methods = ['GET','POST'])
def createPoll():
    if 'credentials' in session:
        if request.method == 'GET':
            return render_template('create_poll.html',error = None)
        else:
            try:
                poll_id = random.randint(100000,999999)
                que = request.form['que']

                options = []
                for i in range(1,len(request.form)):               
                    options.append(request.form['op' + str(i)])

                credentials = session['credentials']

                if que != '' and '' not in options:
                    question = questions(poll_id,credentials.get('email'),que)
                    for option in options:
                        db.session.add(choices(poll_id,option,0))
                    db.session.add(question)
                    db.session.commit() 
                    err = False
                    msg = 'successfully created poll. Poll Id: {}'.format(poll_id)
                else:
                    err = True
                    msg = 'Invalid Input'

                
            except Exception as e:
                print(e)
                err = True
                msg = 'Unable to create poll'
            
            finally:
                if err:
                    return render_template('create_poll.html',error = msg)
                else:
                    flash(msg)
                    return redirect(url_for('home'))
    else:
        return redirect(url_for('login'))
                

@app.route('/giveVote/')
def giveVote():
    if 'credentials' in session:
        if 'poll_id' not in request.args:
            return render_template('enter_poll_id.html',error = None)
        else:
            poll_id = request.args.get('poll_id')
            if poll_id == '':
                return render_template('enter_poll_id.html',error = 'Invalid Poll Id')

            poll_questions = questions.query.filter_by(poll_id = int(poll_id)).all()
            options = choices.query.filter_by(poll_id = int(poll_id)).all()

            if  poll_questions and options:
                question = poll_questions[0].question
                return render_template('votes_result.html',question = question,options = options)
            else:
                return render_template('enter_poll_id.html',error = 'Invalid Poll Id')

    else:
        return redirect(url_for('login'))

@app.route('/viewVoters/')
def viewVoters():
    if 'credentials' in session:
        if 'poll_id' not in request.args:
            return render_template('enter_pollid_viewvote.html')
        else:
            poll_id = request.args.get('poll_id')
            if poll_id == '':
                return render_template('enter_pollid_viewvote.html',error = 'Invalid Poll Id')

            poll_voters = voters.query.filter_by(poll_id = int(poll_id)).all()
            if poll_voters:
                return render_template('voters.html',poll_voters = poll_voters)
            else:
                return render_template('enter_pollid_viewvote.html',error = 'Invalid Poll Id or No one has voted for entered poll_id')
    else:
        return redirect(url_for('login'))

@app.route('/viewCreatedPoll/')
def viewCreatedPoll():
    if 'credentials' in session:
        credentials = session['credentials']
        user_questions = questions.query.filter_by(creator_id = credentials['email']).all()
        return render_template('user_questions.html',user_questions = user_questions)
    else:
        return redirect(url_for('login'))

@app.route('/deletePoll/')
def deletePoll():
    if 'credentials' in session:
        if 'poll_id' not in request.args:
            return render_template('enter_pollid_todelete.html',error = None)
        else:
            poll_id = request.args.get('poll_id')
            if poll_id == '':
                return render_template('enter_pollid_todelete.html',error = 'Invalid Poll Id')
            credentials = session['credentials']
            poll_voters = voters.query.filter_by(poll_id = int(poll_id)).all()
            poll_questions = questions.query.filter_by(poll_id = int(poll_id)).all()
            options = choices.query.filter_by(poll_id = int(poll_id)).all()
            if poll_questions[0].creator_id == credentials['email'] and poll_questions and options:
                for option in options:
                    db.session.delete(option)
                for question in poll_questions:
                    db.session.delete(question)
                for voter in poll_voters:
                    db.session.delete(voter)
                db.session.commit()
                return 'Successfully deleted poll'
            else:
                return render_template('enter_pollid_todelete.html',error = 'Invalid Poll Id ')
    else:
        return redirect(url_for('login'))



@socketio.on('givevote')
def print_res(res):
    hasVoted = False
    poll_id = res['poll_id']
    if 'credentials' in session:
        credentials = session['credentials']
        for voter in voters.query.filter_by(voter_email = credentials['email']).all():
            if voter.poll_id == int(poll_id):
                hasVoted = True
                break
        
        if not hasVoted:
            voter = voters(poll_id,credentials['email'],credentials['name'])
            db.session.add(voter)
            choice = choices.query.filter_by(choice_id = res['choice_id']).first()
            vote = choice.vote
            vote = vote + 1
            choice.vote = vote
            db.session.commit()
            res['vote'] = vote
            emit('updateVote',res,room=poll_id)
        else:
            emit('showError',{'errMsg' : 'You have already voted'})
    else:
        emit('showError',{'errMsg' : 'Your session is expired'})

@socketio.on('joinRoom')
def joinRoom(res):
    join_room(res['poll_id'])
    print('joined')


@socketio.on('connect')
def test():
    print('connected')



        



if __name__ == '__main__':
    db.create_all()
    socketio.run(app)

