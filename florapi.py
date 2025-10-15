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
from cheroot import wsgi
import psycopg2
import config as cfg
from flasgger import Swagger, LazyString, LazyJSONEncoder
from flasgger import swag_from

# --- CONFIGURATION à adapter ---
ODOO_PATH = '/opt/odoo18/odoo18'          # chemin vers dossier odoo (avec odoo/__init__.py)
custom_addons = '/opt/odoo18/odoo18/custom-addons'
DB_NAME = 'ou18'                              # nom de ta base de données Odoo
DB_USER = 'odoo18'
# --- Ajout du chemin Odoo au PYTHONPATH ---
sys.path.append(ODOO_PATH)
sys.path.append(os.path.dirname(ODOO_PATH))

import odoo
import odoo.modules.registry
from odoo import api, SUPERUSER_ID
import odoo.service.server as server

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

odoo.tools.config['db_host'] = 'localhost'
odoo.tools.config['db_name'] = cfg.db['name']
odoo.tools.config['db_user'] = cfg.db['user']
odoo.tools.config['db_password'] = cfg.db['password']
odoo.tools.config['without_demo'] = True
odoo.tools.config['log_level'] = 'info'
odoo.tools.config['addons_path'] = f'{ODOO_PATH}/addons,{custom_addons}'

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
        if request.headers.get('x-api-key') and request.headers.get('x-api-key') == key:
            return view_function(*args, **kwargs)
        else:
            abort(401)
    return decorated_function

def getOdooAdhId(email):
    webLogger.info(LOG_HEADER+" getOdooAdhId")
    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        filters2 = [('email', '=', email)]
        partners = env['res.partner'].search(filters2, limit=1)
        return partners.id

def getOdooAdhpros(filters):
    webLogger.info(LOG_HEADER+" getOdooAdhpros")
    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        filters2 = [('is_company', '=', True)]
        for x, y in filters.items():
            if (y=="'t'"):
                filters2.append((x, '=', True))
            elif (y=="'f'"):
                filters2.append((x, '=', False))
            else:
                filters2.append((x, 'like', y.upper()))
        partners = env['res.partner'].search(filters2)

        data = partners.read([
            'name', 
            'email',
            'contact_email', 
            'street', 
            'zip', 
            'city', 
            'phone', 
            'is_organization',
            'membership_state', 
            'membership_start', 
            'membership_stop', 
            'account_cyclos',
            'orga_choice',
            'detailed_activity',
            'currency_exchange_office',
            'changeeuros',
            'prvlt_sepa',
            'write_date'
        ])
        json_output = json.dumps(data, indent=4, default=str)
        return json_output

def getOdooAdhs(filters):
    webLogger.info(LOG_HEADER+" getOdooAdhs")
     # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        filters2 = [('is_company', '=', False)]
        for x, y in filters.items():
            if ((x == "lastname") or (x == "firstname")):
                filters2.append(('name', 'like', '%'+y.upper()+'%'))
            else:
                filters2.append((x, '=', y.upper()))
        partners = env['res.partner'].search(filters2)
        
        #data = partners.read(['name'])
        data = partners.read([
            'name', 
            'email', 
            'street', 
            'zip', 
            'city', 
            'phone', 
            'ref', 
            'membership_state', 
            'membership_start', 
            'membership_stop', 
            'account_cyclos',
            'orga_choice',
            'accept_newsletter',
            'changeeuros',
            'prvlt_sepa',
            'write_date'
        ])
        json_output = json.dumps(data, indent=4, default=str)
        return json_output

def getOdooAssos(filters):
    webLogger.info(LOG_HEADER+" getOdooAssos")
    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        filters2 = [('is_company', '=', True), ('active', '=', True), ('is_organization', '=', True)]
        for x, y in filters.items():
            if (y=="'t'"):
                filters2.append((x, '=', True))
            elif (y=="'f'"):
                filters2.append((x, '=', False))
            else:
                filters2.append((x, 'like', y.upper()))
        partners = env['res.partner'].search(filters2)

        data = partners.read([
            'name', 
            'email',
            'contact_email', 
            'street', 
            'zip', 
            'city', 
            'phone', 
            'is_organization',
            'membership_state', 
            'membership_start', 
            'membership_stop', 
            'account_cyclos',
            'orga_choice',
            'detailed_activity',
            'currency_exchange_office',
            'changeeuros',
            'prvlt_sepa',
            'write_date'
        ])
        json_output = json.dumps(data, indent=4, default=str)
        return json_output

def getFreeOdooRef():
    webLogger.info(LOG_HEADER+" getFreeOdooRef")
    firstRef = 10000
    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        filters2 = [('is_company', '=', False), ('active', '=', True), ('ref', '!=', False)]
        partners = env['res.partner'].search(filters2)

        numeric_refs = [int(p.ref) for p in partners if p.ref.isdigit()]
        max_ref = max(numeric_refs) if numeric_refs else None
        return max_ref+1

# def getOdooAccountInvoiceSeq():
#     webLogger.info(LOG_HEADER+" getOdooAccountInvoiceSeq")
#     connection = connect()
#     if (connection != None):
#         try:
#             with connection.cursor() as cursor:
#                 sql = "SELECT last_value from account_invoice_id_seq;"
#                 webLogger.debug(LOG_HEADER+" "+sql)
#                 cursor.execute(sql)
#                 resultsSQL = cursor.fetchall()
#                 return resultsSQL[0][0]
#         finally:
#             connection.close()

"""
def getOdooLastInvoice():
    webLogger.info(LOG_HEADER+" getOdooLastInvoice ")
    connection = connect()
    #id = getOdooAccountInvoiceSeq()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                #sql = "SELECT id,number,move_name,reference from account_invoice where id="+str(id)+";"
                sql = "select sequence_prefix,name from account_move order by name desc;"
                webLogger.debug(LOG_HEADER+" "+sql)
                cursor.execute(sql)
                resultsSQL = cursor.fetchall()
                m = re.match(resultsSQL[0][0]+"(\d+)", resultsSQL[0][1])
                if m:
                    return m.group(1),resultsSQL[0][0]
        finally:
            connection.close()

def getNameForInvoice():
    webLogger.info(LOG_HEADER+" getNameForInvoice ")
    (lastnum,prefix) = getOdooLastInvoice()
    num = int(lastnum)+1
    return prefix+'{:0>5}'.format(num)
"""

def createOdooAdhs(email, infos):
    webLogger.info(LOG_HEADER+" createOdooAdhs")
    for key in infos:
        if isinstance(infos[key], str):
            infos[key] = infos[key].replace("'", "''")
    name = infos['firstname'][0].upper()+infos['firstname'][1:]+" "+infos['lastname'].upper()
    
    datas = {
        'name': name,
        'email': email,
        'phone': infos['phone'],
        'account_cyclos': infos['account_cyclos'],
        'street': infos['street'],
        'zip': infos['zip'],
        'city': infos['city'],
        'is_company': 'f',
        "ref": infos['ref'],
        "changeeuros": infos['changeeuros'],
        "orga_choice": infos['orga_choice'],
        "accept_newsletter": infos['accept_newsletter']
    }

    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})

        datas['country_id'] =  env.ref('base.fr').id
        datas['company_type'] = 'person'
        partner = env['res.partner'].create(datas)

        print(f"Adhérent créé : {partner.name} (ID {partner.id})")
        return partner

def updateOdooAdhs(email, infos):
    webLogger.info(LOG_HEADER+" updateOdooAdhs")
    id = getOdooAdhId(email)
    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        partner = env['res.partner'].browse(id)
        partner.write(infos)
        #partner.write({
        #    'name': 'Nom mis à jour',
        #    'email': 'nouveau@mail.com',
        #})
        return partner

def createMembership(partner_id, amount):
    webLogger.info(LOG_HEADER+" createAccountMove")
    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        product = env['product.product'].search([('name', '=', 'Adh')], limit=1)

        now = datetime.now()
        invoice_date = now.strftime("%Y-%m-%d")
        # Créer une facture simulant l’adhésion (si module "account" activé)
        invoice = env['account.move'].create({
            'partner_id': partner_id,
            'move_type': 'out_invoice',
            'invoice_date': invoice_date,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'quantity': 1,
                'price_unit': amount,
            })],
        })

        now = datetime.now()
        date1 = now.strftime("%Y-%m-%d")
        years_to_add = now.year + 1
        date2 = now.replace(year=years_to_add).strftime('%Y-%m-%d')

        membership_line = env['membership.membership_line'].search([
            ('partner', '=', partner_id),
            ('membership_id', '=', product.id),
            ('account_invoice_id', '=', invoice.id),
        ], limit=1)
        
        membership_line.write({
            'date_from': date1,
            'date_to': date2,
        })
        return membership_line

"""
def updateMembershipLine(membership_id, infos):
    webLogger.info(LOG_HEADER+" updateMembershipLine")
    connection = connect()
    if (connection != None):
        try:
            with connection.cursor() as cursor:
                if infos is not None:
                    for key in infos:
                        if isinstance(infos[key], str):
                            infos[key] = infos[key].replace("'", "''")
                    sql = "UPDATE membership_membership_line SET "
                    i=1
                    for key in infos:
                        if (i < len(infos)):
                            sql += key+"='"+str(infos[key])+"'," 
                        else:
                            sql += key+"='"+str(infos[key])+"' "
                        i=i+1
                    sql += "WHERE id='"+str(membership_id)+"';"
                    webLogger.debug(LOG_HEADER+" "+sql)
                    cursor.execute(sql)
                    connection.commit()
                    return cursor.lastrowid
        finally:
            connection.close()
"""

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
    json_partners = getOdooAdhpros(filters)
    return json_partners

@app.route('/getAdhs', methods=['GET'])
@require_appkey
@swag_from("api/getAdhs.yml")
def getAdhs():
    webLogger.info(LOG_HEADER + '[/getAdhs] GET')
    filters = request.args.to_dict()
    json_partners = getOdooAdhs(filters)
    return json_partners

@app.route('/getAssos', methods=['GET'])
@require_appkey
@swag_from("api/getAssos.yml")
def getAssos():
    webLogger.info(LOG_HEADER + '[/getAssos] GET')
    filters = request.args.to_dict()
    assos = getOdooAssos(filters)
    return assos

"""
@app.route('/getAccountInvoiceSeq', methods=['GET'])
@require_appkey
@swag_from("api/getAccountInvoiceSeq.yml")
def getAccountInvoiceSeq():
    webLogger.info(LOG_HEADER + '[/getAccountInvoiceSeq] GET')
    ref = getOdooAccountInvoiceSeq()
    return jsonify(ref)

@app.route('/getLastInvoice', methods=['GET'])
@require_appkey
@swag_from("api/getLastInvoice.yml")
def getLastInvoice():
    webLogger.info(LOG_HEADER + '[/getLastInvoice] GET')
    infos = getOdooLastInvoice()
    return jsonify(infos)
"""

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
        "account_cyclos",
        "accept_newsletter"
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
    print(json_data)
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
    createMembership(partner_id, json_data['amount'])
    return "200"

"""
@app.route('/postMembershipCompl', methods=['POST'])
@require_appkey
@swag_from("api/postMembershipCompl.yml")
def postMembershipCompl():
    webLogger.info(LOG_HEADER + '[/postMembershipCompl] POST')
    required_args = {
        "email",
        "name",
        "amount"
    }
    json_data = request.get_json(force=True)
    for arg in required_args:
        if arg not in json_data:
            webLogger.error(LOG_HEADER + '[/postMembershipCompl] expected data not found : '+arg)
            return "404"
    print("test3")
    partner_id = getOdooAdhId(json_data['email'])
    invoice_id = createAccountInvoice(partner_id, json_data['amount'], json_data['name'])
    account_invoice_line = createAccountInvoiceLineAdhCompl(partner_id, json_data['amount'], invoice_id)
    return "200"
"""

addr = '0.0.0.0', 80
serverweb = wsgi.Server(addr, app)

if __name__ == '__main__':
    global session
    session=dict()
    try:
        webLogger.info(LOG_HEADER + '[starting server]')
        serverweb.start()
    except KeyboardInterrupt:
        webLogger.info(LOG_HEADER + '[stopping server]')
        serverweb.stop()
