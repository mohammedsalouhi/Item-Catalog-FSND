import string
import random
import requests
from flask import make_response
import json
import httplib2
from oauth2client.client import FlowExchangeError
from oauth2client.client import flow_from_clientsecrets
from flask import session as login_session
from database_setup import Base, Restaurant, MenuItem, User
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from flask import Flask, render_template, request
from flask import redirect, url_for, jsonify, flash
app = Flask(__name__)


# Imports for Oauth2

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())[
    'web']['client_id']


engine = create_engine('sqlite:///restaurantmenuusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/login')
def showLogin():
    state = ''.join(
        random.choice(
            string.ascii_uppercase +
            string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    google_id = credentials.id_token['sub']
    if result['user_id'] != google_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_google_id = login_session.get('google_id')
    if stored_access_token is not None and google_id == stored_google_id:
        response = make_response(json.dumps(
            'Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['google_id'] = google_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)
    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1><hr>'
    output += '<img src="'
    output += login_session['picture']
    output += '" class="rounded-circle" width="300" height="300">'
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

# Disconnect -Revoke a current user's token and reset their login_session


@app.route("/gdisconnect")
def gdisconnect():
    # Only disconnect a connected user
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-type'] = 'application/json'
        return response

    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']

    url = "https://accounts.google.com/o/oauth2/"
    url += "revoke?token=%s" % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is'
    print result

    if result['status'] == '200':
        # Reset the user's session
        del login_session['access_token']
        del login_session['google_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        flash('Successfully disconnected')
        return redirect(url_for('index'))
    else:
        # for whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/')
def index():
    restaurants = session.query(Restaurant).all()
    ten_items = session.query(MenuItem).order_by(MenuItem.id.desc()).limit(10)
    login = True if 'username' in login_session else False
    return render_template(
        'index.html',
        restaurants=restaurants,
        login=login,
        login_session=login_session,
        items=ten_items)


@app.route('/restaurants')
def showRestaurants():
    restaurants = session.query(Restaurant).all()
    login = True if 'username' in login_session else False
    return render_template(
        'restaurants.html',
        restaurants=restaurants,
        login=login,
        login_session=login_session)


@app.route('/restaurants/JSON')
def showRestaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(Restaurants=[i.serialize for i in restaurants])


@app.route('/restaurant/new', methods=["GET", "POST"])
def newRestaurant():
    # return "This page will be for making a new restaurant"
    if 'username' not in login_session:
        flash("You can't add anything you aren't logged in")
        return redirect('/login')
    if request.method == "POST":
        restaurantName = request.form["restaurantName"]
        restaurant = Restaurant(
            name=restaurantName,
            user_id=login_session['user_id'])
        session.add(restaurant)
        flash('New Restaurant "%s" Successfully Created' % restaurant.name)
        session.commit()
        return redirect(url_for('index'))
    else:
        login = True
        return render_template(
            "newRestaurant.html",
            login=login,
            login_session=login_session)


@app.route('/restaurant/<int:restaurant_id>/edit', methods=["GET", "POST"])
def editRestaurant(restaurant_id):
    if 'username' not in login_session:
        flash("You can't edit anything, if you aren't logged in")
        return redirect('/login')
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if restaurant.user_id != login_session['user_id']:
        flash('You are not authorized to make this operation')
        return redirect(url_for('showRestaurants'))
    if request.method == "POST":
        if request.form['editedName']:
            restaurant.name = request.form['editedName']
            session.add(restaurant)
            session.commit()
            flash('Restaurant Successfully Updated to "%s"' % restaurant.name)
            return redirect(url_for("index"))
    else:
        login = True
        return render_template(
            "editRestaurant.html",
            restaurant=restaurant,
            login=login,
            login_session=login_session)


@app.route('/restaurant/<int:restaurant_id>/delete', methods=["GET", "POST"])
def deleteRestaurant(restaurant_id):
    if 'username' not in login_session:
        flash("You can't delete anything, if you aren't logged in")
        return redirect('/login')
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if restaurant.user_id != login_session['user_id']:
        flash('You are not authorized to make this operation')
        return redirect(url_for('index'))
        # return "<script>function myFunction(){alert('You are not authorized
        # to delete this restaurant. Please create your own restaurant in order
        # to delete.');}</script><body onload = 'myFunction()'>"
    if request.method == "POST":
        session.delete(restaurant)
        flash('Restaurant "%s" Successfully Deleted' % restaurant.name)
        session.commit()
        return redirect(url_for("index"))
    else:
        login = True
        return render_template(
            "deleteRestaurant.html",
            restaurant=restaurant,
            login=login,
            login_session=login_session)


@app.route('/restaurant/<int:restaurant_id>/menu')
@app.route('/restaurant/<int:restaurant_id>')
def showMenu(restaurant_id):
    restaurants = session.query(Restaurant).all()
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant_id)
    creator = getUserInfo(restaurant.user_id)
    login = True if 'username' in login_session else False
    auth = True if creator.id == login_session['user_id'] else False
    # return render_template("menu.html", items = items, restaurant =
    # restaurant, restaurants creator = creator, auth = auth, login = login,
    # login_session = login_session)
    return render_template(
        'menuitems.html',
        restaurants=restaurants,
        restaurant=restaurant,
        login=login,
        login_session=login_session,
        items=items,
        creator=creator,
        auth=auth)


@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def showMenuJSON(restaurant_id):
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant_id)
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def showMenuItemJSON(restaurant_id, menu_id):
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(MenuItem=item.serialize)


@app.route('/restaurant/<int:restaurant_id>/menu/new', methods=["GET", "POST"])
def newMenuItem(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if 'username' not in login_session:
        flash("You can't add anything, if you aren't logged in")
        return redirect('/login')
    if request.method == "POST":
        name = request.form['name']
        price = request.form['price']
        description = request.form['description']
        course = request.form['course']
        menuItem = MenuItem(
            name=name,
            price=price,
            description=description,
            course=course,
            restaurant_id=restaurant_id,
            user_id=restaurant.user_id)
        session.add(menuItem)
        session.commit()
        flash('Menu Item "%s" Successfully Created' % menuItem.name)
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
        login = True
        return render_template(
            'newMenu.html',
            restaurant_id=restaurant_id,
            login=login,
            login_session=login_session)


@app.route(
    '/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit',
    methods=[
        "GET",
        "POST"])
def editMenuItem(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if 'username' not in login_session:
        flash("You can't edit anything, if you aren't logged in")
        return redirect('/login')
    if restaurant.user_id != login_session['user_id']:
        flash('You are not authorized to make this operation')
        return redirect(url_for('showRestaurants'))
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    if request.method == "POST":
        item.name = request.form['name'] if request.form['name'] else item.name
        item.price = (
            request.form['price'] +
            " $") if request.form['price'] else item.price
        description = request.form['description']
        item.description = description if description else item.description
        course = request.form['course']
        item.course = course if course else item.course
        session.add(item)
        session.commit()
        flash('Menu Item Successfully Updated to "%s"' % item.name)
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
        login = True
        return render_template(
            'editMenu.html',
            restaurant_id=restaurant_id,
            menu_id=menu_id,
            item=item,
            login=login,
            login_session=login_session)


@app.route(
    '/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete',
    methods=[
        "GET",
        "POST"])
def deleteMenuItem(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if 'username' not in login_session:
        flash("You can't delete anything, if you aren't logged in")
        return redirect('/login')
    if restaurant.user_id != login_session['user_id']:
        flash('You are not authorized to make this operation')
        return redirect(url_for('showRestaurants'))
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    if request.method == "POST":
        session.delete(item)
        flash('Menu Item "%s" Successfully Deleted' % item.name)
        session.commit()
        return redirect(url_for('showMenu', restaurant_id=restaurant_id))
    else:
        login = True
        return render_template(
            'deleteMenu.html',
            restaurant_id=restaurant_id,
            menu_id=menu_id,
            item=item,
            login=login,
            login_session=login_session)


def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except BaseException:
        return None


if __name__ == "__main__":
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000, threaded=False)
