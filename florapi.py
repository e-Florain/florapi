#!/usr/bin/env python

import sys
import logging
import os
import json
import re
import time
from functools import wraps
from logging.handlers import RotatingFileHandler
import threading  # launch server in a thread
import requests  # make http request to shutdown web server
from flask import Flask, request, redirect, url_for, render_template, abort, jsonify
import time, signal
from cherrypy import wsgiserver
import psycopg2
import config as cfg
from flasgger import Swagger, LazyString, LazyJSONEncoder
from flasgger import swag_from

LOG_HEADER = " [" + __file__ + "] - "
p = re.compile("\w+(\d)")
LOG_PATH = os.path.dirname(os.path.abspath(__file__)) + '/log/'
logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
webLogger = logging.getLogger('florapi')
webLogger.setLevel(logging.DEBUG)
webLogger.propagate = False
fileHandler = RotatingFileHandler("{0}/{1}.log".format(LOG_PATH, 'florapi'), maxBytes=2000000,
                                  backupCount=1500)
fileHandler.setFormatter(logFormatter)
webLogger.addHandler(fileHandler)

app = Flask(__name__)

# Create an APISpec
template = {
  "swagger": "2.0",
  "info": {
    "title": "FlorAPI Swagger",
    "description": "FlorAPI Swagger",
    "version": "0.1.1",
    "contact": {
      "name": "Le Florain",
      "url": "https://florain.fr",
    }
  },
  "securityDefinitions": {
    "Bearer": {
      "type": "apiKey",
      "name": "x-api-key",
      "in": "header",
      "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
    }
  },
  "security": [
    {
      "Bearer": [ ]
    }
  ]

}

app.config['SWAGGER'] = {
    'title': 'FlorAPI',
    'uiversion': 3,
    "specs_route": "/swagger/"
}
swagger = Swagger(app, template= template)


def require_appkey(view_function):
    @wraps(view_function)
    # the new, post-decoration function. Note *args and **kwargs here.
    def decorated_function(*args, **kwargs):
        with open(os.path.dirname(os.path.abspath(__file__)) + '/api.key', 'r') as apikey:
            key=apikey.read().replace('\n', '')
        #if request.args.get('key') and request.args.get('key') == key:
        if request.headers.get('x-api-key') and request.headers.get('x-api-key') == key:
            return view_function(*args, **kwargs)
        else:
            abort(401)
    return decorated_function

def getOdooAdhpros(filters):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * from res_partner where is_company='t' and active='t'"
                for x, y in filters.items():
                    if ((x == "name") or (x == "email")):
                        sql += " and upper("+x+") like upper('%"+y+"%')"
                    else:
                        sql += " and "+x+"='"+y+"'"
                sql += ";"
                cursor.execute(sql)
                resultsSQL = cursor.fetchall()

                cursor.execute("SELECT * from res_partner LIMIT 0")
                colnames = [desc[0] for desc in cursor.description]
                return (colnames, resultsSQL)
        finally:
            connection.close()

def getOdooAdhs(filters):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * from res_partner where is_company='f' and active='t'"
                #print(filters)
                for x, y in filters.items():
                    if ((x == "lastname") or (x == "firstname") or (x == "email")):
                        sql += " and upper("+x+") like upper('%"+y+"%')"
                    else:
                        sql += " and "+x+"='"+y+"'"
                sql += ";"
                #print(sql)
                cursor.execute(sql)
                resultsSQL = cursor.fetchall()

                cursor.execute("SELECT * from res_partner LIMIT 0")
                colnames = [desc[0] for desc in cursor.description]
                return (colnames, resultsSQL)
        finally:
            connection.close()

def connect():
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # connect to the PostgreSQL server
        webLogger.info(LOG_HEADER + '[-] '+'Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(
            host="localhost",
            user=cfg.db['user'],
            password=cfg.db['password'],
            database=cfg.db['name'])
        return conn        
    except (Exception, psycopg2.DatabaseError) as error:
        webLogger.error(LOG_HEADER + str(error))

@app.route('/json/', methods=['POST'])
@require_appkey
def put_user():
    return 'Posted JSON!'

@app.route('/getAdhpros', methods=['GET'])
@require_appkey
@swag_from("api/getAdhpros.yml")
def getAdhpros():
    webLogger.info(LOG_HEADER + '[/getAdhpros] GET')
    filters = request.args.to_dict()
    pgsql_headers = {
        "name": "",
        "street": "",
        "zip": "",
        "city": "",
        "email": "",
        "phone": "",
        "membership_state": "",
        "account_cyclos": ""
    }
    list_adhpros = []
    (cols, adhpros) = getOdooAdhpros(filters)
    i = 0
    for col in cols:
        for header in pgsql_headers:
            if (col == header):
                pgsql_headers[header] = i
        i+=1
    for adhpro in adhpros:
        adhpros_dict = {}
        for x, y in pgsql_headers.items():
            adhpros_dict[x] = adhpro[y]
        list_adhpros.append(adhpros_dict)
    return jsonify(list_adhpros)

@app.route('/getAdhs', methods=['GET'])
@require_appkey
@swag_from("api/getAdhs.yml")
def getAdhs():
    webLogger.info(LOG_HEADER + '[/getAdhs] GET')
    filters = request.args.to_dict()
    #print(filters)
    #print(data['account_cyclos'])
    pgsql_headers = {
        "firstname": "",
        "lastname": "",
        "ref": "",
        "email": "",
        "membership_state": "",
        "account_cyclos": ""
    }
    list_adhs = []
    (cols, adhs) = getOdooAdhs(filters)
    i = 0
    for col in cols:
        for header in pgsql_headers:
            if (col == header):
                pgsql_headers[header] = i
        i+=1
    for adh in adhs:
        adhs_dict = {}
        for x, y in pgsql_headers.items():
            adhs_dict[x] = adh[y]
        list_adhs.append(adhs_dict)
    return jsonify(list_adhs)

d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
server = wsgiserver.CherryPyWSGIServer(('0.0.0.0', 80), d)

if __name__ == '__main__':
    global session
    session=dict()
    try:
        webLogger.info(LOG_HEADER + '[starting server]')
        server.start()
    except KeyboardInterrupt:
        webLogger.info(LOG_HEADER + '[stopping server]')
        server.stop()
