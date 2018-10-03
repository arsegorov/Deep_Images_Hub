from flask import render_template
from app import app
from app.forms import LoginForm
from app.DAO import get_featured_batches

# TODO - Fix his qucik and dirty ways to make query with proper SQLAlchemy style

@app.route('/')
@app.route('/index')
def index():
    user = {'username': 'Heng'}


    features = get_featured_batches()



    return render_template('index.html', title='Home', user=user, features=features)

@app.route('/')
def static_file():
    return app.send_static_file('index.html')

@app.route('/login')
def login():
    form = LoginForm()
    return render_template('login.html', title='Sign In', form=form)

if __name__ == '__main__':
   app.run(debug = True)