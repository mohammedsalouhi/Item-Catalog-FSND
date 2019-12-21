# Item Catalog Web App (FSND)
This is my Item catalog project for Udacity FSND

## About
This application provides a list of Menu within a variety of Restaurants as well as provide a user registration and authentication system using OAuth. Registered users will have the ability to post, edit and delete their own items.

## Requirements
* [vagrant](https://www.vagrantup.com/downloads.html)
* [VirtualBox](https://www.virtualbox.org/wiki/Downloads)
* [Udacity vagrantfile](https://github.com/udacity/fullstack-nanodegree-vm)
* [Python2](https://www.python.org/downloads/)
* [Flask framework]() by typing `pip install -U Flask` in the terminal inside vm
* [SQLAlchemy]() by typing `pip install SQLAlchemy`
* [OAuth google credentials](https://console.developers.google.com/project/_/apiui/apis/library)

## How to Run it
1. Install VirtualBox and Vagrant
2. Clone The Udacity vagrantfile
3. Go inside the vagrant directory of the cloned udacity's file
4. Download this file, delete .git dir, and then move it inside the vagrant directory of udacity vm
5. cd to directory that you have just moved
6. Change the client_secret.json file with the youre, make sure the javascript origin and redirect uri correspond
7. Run `python database_setup.py`, this command initialize the database
8. Then run `python lotsofmenus.py`, to populate the database
9. And Finally run `python finalproject.py`

## JSON Endpoints
* /restaurant/<restaurant_id>/menu/<menu_id>/JSON
* /restaurant/<restaurant_id>/menu/JSON
* /restaurants/JSON
