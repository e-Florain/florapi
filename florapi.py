#!/usr/bin/env python

import sys
import logging
import os
import json
import re
import time
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
import threading  # launch server in a thread
import requests  # make http request to shutdown web server
from flask import Flask, request, redirect, url_for, render_template, abort, jsonify
from flask_restful import Api, Resource, reqparse
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

def getOdooAdhId(email):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                sql = "SELECT id from res_partner where email='"+email+"';"
                cursor.execute(sql)
                resultsSQL = cursor.fetchall()
                return resultsSQL[0][0]
        finally:
            connection.close()

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

def getOdooAssos(filters):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * from res_partner where is_company='t' and active='t' and is_organization='t' order by name"
                #print(filters)
                for x, y in filters.items():
                    if ((x == "name") or (x == "email")):
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

def getFreeOdooRef():
    connection = connect()
    firstRef = 4000
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                sql = "SELECT ref from res_partner where is_company='f' and active='t' order by ref;"
                cursor.execute(sql)
                ids = []
                resultsSQL = cursor.fetchall()
                for id in resultsSQL:
                    ids.append(id[0])
                found=False
                ref = firstRef
                while found == False:
                    if (str(ref) not in ids):
                        found = True
                    else:
                        ref=ref+1
                return ref
        finally:
            connection.close()

def createOdooAdhs(email, infos):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                name = infos['firstname'][0].upper()+infos['firstname'][1:]+" "+infos['lastname'].upper()
                now = datetime.now()
                dt_string = now.strftime("%d/%m/%Y %H:%M:%S.%f")
                sql = "INSERT INTO res_partner (name, display_name, firstname, lastname, ref, phone, email, active, lang, customer, supplier, employee, is_company, is_published, to_renew, is_volunteer, currency_exchange_office, is_adhered_member, free_member, contact_type, membership_state, create_uid, write_uid, write_date, street, zip, city, orga_choice, account_cyclos, create_date, write_date) VALUES ('"+name+"', '"+name+"', '"+infos['firstname']+"', '"+infos['lastname']+"', '"+str(infos['ref'])+"', '"+infos['phone']+"', '"+email+"', 't', 'fr_FR', 't', 'f', 'f', 'f', 'f', 'f', 'f', 'f', 'f', 'f', 'standalone', 'none', 2, 2, '"+dt_string+"', '"+infos['street']+"', '"+infos['zip']+"', '"+infos['city']+"', '"+infos['orga_choice']+"', '"+infos['account_cyclos']+"', '"+str(now)+"', '"+str(now)+"');"
                # select name,ref,phone,email from res_partner where is_company='f';
                # print (sql)
                cursor.execute(sql)
                connection.commit()
                return cursor.lastrowid
        finally:
            connection.close()

def updateOdooAdhs(email, infos):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                if infos is not None:
                    sql = "UPDATE res_partner SET "
                    i=1
                    for key in infos:
                        if (i < len(infos)):
                            sql += key+"='"+infos[key]+"'," 
                        else:
                            sql += key+"='"+infos[key]+"' "
                        i=i+1
                    sql += "WHERE email='"+email+"';"
                    #print(sql)
                    cursor.execute(sql)
                    connection.commit()
                    return cursor.lastrowid
        finally:
            connection.close()

def createMembershipLine(partner_id, account_invoice_line, amount):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                if partner_id is not None:
                    now = datetime.now()
                    dt_string = now.strftime("%Y-%m-%d")
                    years_to_add = now.year + 1
                    dt_string2 = now.replace(year=years_to_add).strftime('%Y-%m-%d')

                    sql = "INSERT INTO membership_membership_line (partner, membership_id, date_from, date_to, date, member_price, account_invoice_line, company_id, state, create_date, write_date) VALUES ("+str(partner_id)+", 1, '"+dt_string+"', '"+dt_string2+"', '"+dt_string+"', '"+amount+"', "+str(account_invoice_line)+", 1, 'waiting', '"+str(now)+"', '"+str(now)+"') RETURNING id;"
                    cursor.execute(sql)
                    id_of_new_row = cursor.fetchone()[0]
                    connection.commit()
                    return id_of_new_row
        finally:
            connection.close()


def createAccountInvoice(partner_id, amount, name):
    print("createAccountInvoice")
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                if partner_id is not None:
                    now = datetime.now()
                    sql = "INSERT INTO account_invoice (type, state, sent, partner_id, account_id, amount_untaxed, amount_untaxed_signed, amount_total, amount_total_signed, amount_total_company_signed, currency_id, journal_id, company_id, reconciled, residual, residual_signed, residual_company_signed, user_id, vendor_display_name, reference_type, create_date, write_date) VALUES('out_invoice', 'draft', 'f', "+str(partner_id)+", 281, '"+amount+"', '"+amount+"', '"+amount+"', '"+amount+"', '"+amount+"', 1, 1, 1, 't', '0.00', '0.00', '0.00', 2, '"+name+"', 'none', '"+str(now)+"', '"+str(now)+"') RETURNING id;"
                    #print (sql)
                    cursor.execute(sql)
                    id_of_new_row = cursor.fetchone()[0]
                    connection.commit()
                    return id_of_new_row
        finally:
            connection.close()

def createAccountInvoiceLine2022(partner_id, amount, invoice_id):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                if partner_id is not None:
                    now = datetime.now()
                    sql = "INSERT INTO account_invoice_line(name, sequence, invoice_id, uom_id, product_id, account_id, price_unit, price_subtotal, price_total, price_subtotal_signed, quantity, discount, company_id, partner_id, currency_id, is_rounding_line, create_date, write_date) VALUES ('[Adh2022] Adh2022', '10', "+str(invoice_id)+", 1, 2, 636, '"+amount+"', '"+amount+"', '"+amount+"', '"+amount+"', '1.00', '0.00', 1, "+partner_id+", 1, 'f', '"+str(now)+"', '"+str(now)+"') RETURNING id;"
                    cursor.execute(sql)
                    id_of_new_row = cursor.fetchone()[0]
                    connection.commit()
                    return id_of_new_row
        finally:
            connection.close()

def createAccountInvoiceLine(partner_id, amount, invoice_id):
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                if partner_id is not None:
                    now = datetime.now()
                    sql = "INSERT INTO account_invoice_line(name, sequence, invoice_id, uom_id, product_id, account_id, price_unit, price_subtotal, price_total, price_subtotal_signed, quantity, discount, company_id, partner_id, currency_id, is_rounding_line, create_date, write_date) VALUES ('[Adh] Adh', '10', "+str(invoice_id)+", 1, 1, 636, '"+amount+"', '"+amount+"', '"+amount+"', '"+amount+"', '1.00', '0.00', 1, "+partner_id+", 1, 'f', '"+str(now)+"', '"+str(now)+"') RETURNING id;"
                    cursor.execute(sql)
                    id_of_new_row = cursor.fetchone()[0]
                    connection.commit()
                    return id_of_new_row
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
        "id": "",
        "name": "",
        "street": "",
        "zip": "",
        "city": "",
        "email": "",
        "phone": "",
        "detailed_activity": "",
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
        "id": "",
        "firstname": "",
        "lastname": "",
        "street": "",
        "zip": "",
        "city": "",
        "ref": "",
        "email": "",
        "phone": "",
        "membership_state": "",
        "membership_start": "",
        "membership_stop": "",
        "account_cyclos": "",
        "orga_choice": ""
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

@app.route('/getAssos', methods=['GET'])
@require_appkey
@swag_from("api/getAssos.yml")
def getAssos():
    webLogger.info(LOG_HEADER + '[/getAssos] GET')
    filters = request.args.to_dict()
    #print(filters)
    #print(data['account_cyclos'])
    pgsql_headers = {
        "id": "",
        "name": "",
        "street": "",
        "zip": "",
        "city": "",
        "email": "",
        "phone": "",
        "detailed_activity": "",
        "membership_state": "",
        "account_cyclos": ""
    }
    list_assos = []
    (cols, assos) = getOdooAssos(filters)
    i = 0
    for col in cols:
        for header in pgsql_headers:
            if (col == header):
                pgsql_headers[header] = i
        i+=1
    for asso in assos:
        assos_dict = {}
        for x, y in pgsql_headers.items():
            assos_dict[x] = asso[y]
        list_assos.append(assos_dict)
    return jsonify(list_assos)

@app.route('/getFreeRef', methods=['GET'])
@require_appkey
@swag_from("api/getFreeRef.yml")
def getFreeRef():
    webLogger.info(LOG_HEADER + '[/getFreeRef] GET')
    ref = getFreeOdooRef()
    return jsonify(ref)

@app.route('/postAdhs', methods=['POST'])
@require_appkey
@swag_from("api/postAdhs.yml")
def postAdhs():
    webLogger.info(LOG_HEADER + '[/postAdhs] POST')
    required_args = {
        "firstname",
        "lastname",
        "phone",
        "ref",
        "account_cyclos"
    }
    json_data = request.get_json(force=True)
    for arg in required_args:
        if arg not in json_data['infos']:
            webLogger.error(LOG_HEADER + '[/postAdhs] expected data not found : '+arg)
            return "404"
    createOdooAdhs(json_data['email'], json_data['infos'])
    #infos = request.args.to_dict()
    #print(infos)
    return "200"

@app.route('/putAdhs', methods=['POST'])
@require_appkey
@swag_from("api/putAdhs.yml")
def putAdhs():
    webLogger.info(LOG_HEADER + '[/putAdhs] POST')
    json_data = request.get_json(force=True)
    updateOdooAdhs(json_data['email'], json_data['infos'])
    return "200"

@app.route('/postMembership', methods=['POST'])
@require_appkey
@swag_from("api/postMembership.yml")
def postMembership():
    webLogger.info(LOG_HEADER + '[/postMembership] POST')
    required_args = {
        "email",
        "name",
        "amount"
    }
    json_data = request.get_json(force=True)
    for arg in required_args:
        if arg not in json_data:
            webLogger.error(LOG_HEADER + '[/postMembership] expected data not found : '+arg)
            return "404"
    partner_id = getOdooAdhId(json_data['email'])
    invoice_id = createAccountInvoice(partner_id, json_data['amount'], json_data['name'])
    account_invoice_line = createAccountInvoiceLine(partner_id, json_data['amount'], invoice_id)
    createMembershipLine(partner_id, account_invoice_line, json_data['amount'])
    infos = {
        "membership_state": "waiting"
    }
    updateOdooAdhs(json_data['email'], infos)
    # Update adh to waiting
    return "200"

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
