import joblib
import json
import pickle
import os
import pandas as pd
from flask import Flask, jsonify, request
from peewee import (
    SqliteDatabase, PostgresqlDatabase, Model, IntegerField,
    FloatField, TextField, IntegrityError
)
from playhouse.shortcuts import model_to_dict
from playhouse.db_url import connect

DB = connect(os.environ.get('DATABASE_URL') or 'sqlite:///prediction.db')

class Prediction(Model):
    observation_id = IntegerField(unique=True)
    observation = TextField()
    proba = FloatField()
    true_class = IntegerField(null=True)

    class Meta:
        database = DB


DB.create_tables([Prediction], safe=True)

with open('tmp/columns.json') as fh:
    columns = json.load(fh)


with open('tmp/dtypes.pickle', 'rb') as fh:
    dtypes = pickle.load(fh)


pipeline = joblib.load('tmp/pipeline.pickle')


app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    obs_dict = request.get_json()
    _id = obs_dict['id']
    observation = obs_dict['observation']
    try:
        obs = pd.DataFrame([observation], columns=columns).astype(dtypes)
    except ValueError:
        error_msg = "Observation is invalid!"
        response = {"error": error_msg}
        return response

    proba = pipeline.predict_proba(obs)[0, 1]
    response = {'proba': proba}
    p = Prediction(
        observation_id=_id,
        proba=proba,
        observation=request.data
    )
    try:
        p.save()
    except IntegrityError:
        error_msg = "ERROR: Observation ID: '{}' already exists".format(_id)
        response["error"] = error_msg
        print(error_msg)
        DB.rollback()
    return jsonify(response)


@app.route('/update', methods=['POST'])
def update():
    obs = request.get_json()
    try:
        p = Prediction.get(Prediction.observation_id == obs['id'])
        p.true_class = obs['true_class']
        p.save()
        return jsonify(model_to_dict(p))
    except Prediction.DoesNotExist:
        error_msg = 'Observation ID: "{}" does not exist'.format(obs['id'])
        return jsonify({'error': error_msg})

# End webserver stuff
########################################

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True, port=5000)

