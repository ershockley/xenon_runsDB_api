import os
import json
import flask
import json
import flask_praetorian
import flask_sqlalchemy
import tempfile
from datetime import datetime
from flask import url_for
from flask_restful import Resource, Api
from flask_pymongo import PyMongo
from bson import ObjectId
from bson.json_util import dumps
from marshmallow import Schema, fields
from webargs.flaskparser import use_kwargs, use_args

config_file = os.path.join(os.getcwd(), "config", "api_server_config.json")

with open(config_file) as json_data:
    config = json.load(json_data)


app = flask.Flask(__name__)
db = flask_sqlalchemy.SQLAlchemy()
guard = flask_praetorian.Praetorian()


# Initialize a local database for the example
USERDB_URL = os.environ.get('USERDB_URL')
if not USERDB_URL:
    USERDB_URL = config["user_auth"]["database"]["default_url"]
app.config['SQLALCHEMY_DATABASE_URI'] = USERDB_URL
db.init_app(app)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


MONGO_URL = os.environ.get('MONGO_URL')
if not MONGO_URL:
    MONGO_URL = config["runsDB"]["default_url"]


app.json_encoder = JSONEncoder

app.config['MONGO_URI'] = MONGO_URL
mongo = PyMongo(app)

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = config["user_auth"]["jwt"]["default_secret"]

app.config['SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_LIFESPAN'] = config["user_auth"][
    "jwt"]["access_token_lifespan"]
app.config['JWT_REFRESH_LIFESPAN'] = config["user_auth"][
    "jwt"]["refresh_token_lifespan"]

from xenon_runsDB_api.common import user

guard.init_app(app, user.User)

def output_json(obj, code, headers=None):
    resp = flask.make_response(dumps(obj), code)
    resp.headers.extend(headers or {})
    return resp


DEFAULT_REPRESENTATIONS = {'application/json': output_json}
api = Api(app)
api.representations = DEFAULT_REPRESENTATIONS


from xenon_runsDB_api.run import run, gains, data
from xenon_runsDB_api.runs import status, list, tag, query, detector, location, processing_version, source


class Root(Resource):
    def get(self):
        return {
            'status': 'OK',
            'mongo': str(mongo.db),
        }


api.add_resource(Root, '/')


class SiteMap(Resource):
    def get(self):
        return flask.jsonify(
            {"routes": ['%s' % rule for rule in app.url_map.iter_rules()]})


api.add_resource(SiteMap, '/sitemap')


user_args = {
    "username": fields.String(required=True),
    "password": fields.String(required=True)
}


class Login(Resource):
    @use_args(user_args, locations=["json"])
    def post(self, args):
        user = guard.authenticate(args["username"], args["password"])
        ret = {'access_token': guard.encode_jwt_token(user)}
        print(ret)
        return flask.jsonify(ret)

api.add_resource(Login, '/login')


class RefreshToken(Resource):
    # header
    def get(self):
        old_token = guard.read_token_from_header()
        new_token = guard.refresh_jwt_token(old_token)
        ret = {'access_token': new_token}
        return flask.jsonify(ret)

api.add_resource(RefreshToken, "/refresh")


class AddUser(Resource):
    @use_args(user_args, locations=["json"])
    @flask_praetorian.roles_required('admin')
    def post(self, args):
        pass

api.add_resource(AddUser, '/adduser')