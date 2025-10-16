import sys
import os
import requests
import json
import config as cfg
from datetime import datetime

# --- CONFIGURATION à adapter ---
ODOO_PATH = '/opt/odoo18/odoo18'          # chemin vers dossier odoo (avec odoo/__init__.py)
custom_addons = '/opt/odoo18/odoo18/custom-addons'
API_KEY = 'XXXX'
OLD_ODOO_URL = "https://XXXX"
# --- Ajout du chemin Odoo au PYTHONPATH ---
sys.path.append(ODOO_PATH)
sys.path.append(os.path.dirname(ODOO_PATH))

import odoo
import odoo.modules.registry
from odoo import api, SUPERUSER_ID
import odoo.service.server as server

def create_adh(env, infos):
    # Création d'un adhérent
    infos['country_id'] =  env.ref('base.fr').id
    #infos['company_type'] = 'person'
    partner = env['res.partner'].create(infos)

    print(f"Adhérent créé : {partner.name} (ID {partner.id})")
    return partner

def create_invoice(env, partner, price, invoice_date):
    product = env['product.product'].search([('name', '=', 'Adh')], limit=1)

    # Créer une facture simulant l’adhésion (si module "account" activé)
    invoice = env['account.move'].create({
        'partner_id': partner.id,
        'move_type': 'out_invoice',
        'invoice_date': invoice_date,
        'invoice_line_ids': [(0, 0, {
            'product_id': product.id,
            'quantity': 1,
            'price_unit': price,
        })],
    })

    # Valider la facture (optionnel)
    invoice.action_post()
    return invoice

def create_membership(env, partner, invoice, date1, date2):
    product = env['product.product'].search([('name', '=', 'Adh')], limit=1)
    # Rechercher la ligne de membership créée automatiquement
    membership_line = env['membership.membership_line'].search([
        ('partner', '=', partner.id),
        ('membership_id', '=', product.id),
        ('account_invoice_id', '=', invoice.id),
    ], limit=1)
      
    membership_line.write({
        'date_from': date1,
        'date_to': date2,
    })    


def get_memberships(partnerid):
    headers = {'x-api-key': API_KEY, 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(OLD_ODOO_URL+'/getMemberships?partner='+str(partnerid), params={}, headers=headers, verify=False)
    results = json.loads(resp.text)
    return results

def get_new_asso_id(env, email):
    filters2 = [('email', '=', email)]
    partners = env['res.partner'].search(filters2, limit=1)
    return partners.id

def create_oldodoo_adhpro(env):
    headers = {'x-api-key': API_KEY, 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(OLD_ODOO_URL+'/getAdhpros', params={}, headers=headers, verify=False)
    results = json.loads(resp.text)
    for result in results:
        #print(result['name']+" "+str(result['id']))
        #print(result)
        infos = {
            'name': result['name'],
            'email': result['email'],
            'contact_email': result['email'],
            'phone': result['phone'],
            'account_cyclos': 't',
            'street': result['street'],
            'zip': result['zip'],
            'city': result['city'],
            'is_company': 't',
            'prvlt_sepa': result['prvlt_sepa'],
            'is_organization': result['is_organization'],
            'detailed_activity': result['detailed_activity'],
            'currency_exchange_office': result['currency_exchange_office']
        }
        partner = create_adh(env, infos)
        memberships = get_memberships(result['id'])
        for membership in memberships:
            date1 = datetime.strptime(membership[3], "%a, %d %b %Y %H:%M:%S %Z")
            date2 = datetime.strptime(membership[4], "%a, %d %b %Y %H:%M:%S %Z")          
            invoice = create_invoice(env, partner, membership[7], date1)
            membership = create_membership(env, partner, invoice, date1, date2)

def create_oldodoo_adh(env):
    headers = {'x-api-key': API_KEY, 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(OLD_ODOO_URL+'/getAssos', params={}, headers=headers, verify=False)
    resultassos = json.loads(resp.text)
    assos = {}
    defaultasso = ""
    for resultasso in resultassos:
        assos[resultasso['id']] = get_new_asso_id(env,resultasso['email'])
        if (resultasso['email'] == 'cyclos@florain.fr'):
            defaultasso = get_new_asso_id(env,resultasso['email'])
    #print(assos)

    headers = {'x-api-key': API_KEY, 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(OLD_ODOO_URL+'/getAdhs', params={}, headers=headers, verify=False)
    resultadhs = json.loads(resp.text)
    for result in resultadhs:
        #print(result)
        #print(result['orga_choice'])
        #print(result)
        if (result['firstname'] == None):
            firstname = ""
        else:
            firstname = result['firstname']
        if (result['lastname'] == None):
            lastname = ""
        else:
            lastname = result['lastname']
        print(firstname+" "+lastname)
        infos = {
            'name': firstname+" "+lastname,
            'email': result['email'],
            'phone': result['phone'],
            'account_cyclos': result['account_cyclos'],
            'street': result['street'],
            'zip': result['zip'],
            'city': result['city'],
            'ref': result['ref'],
            'is_company': False,
            'prvlt_sepa': result['prvlt_sepa'],
            'accept_newsletter': result['accept_newsletter'],
            'changeeuros': result['changeeuros']
        }
        if (result['orga_choice'] in assos):
            infos['orga_choice'] = assos[result['orga_choice']]
        else:
            infos['orga_choice'] = defaultasso
        partner = create_adh(env, infos)
        memberships = get_memberships(result['id'])
        for membership in memberships:
            date1 = datetime.strptime(membership[3], "%a, %d %b %Y %H:%M:%S %Z")
            date2 = datetime.strptime(membership[4], "%a, %d %b %Y %H:%M:%S %Z")          
            invoice = create_invoice(env, partner, membership[7], date1)
            membership = create_membership(env, partner, invoice, date1, date2)
        

def main():
    # Initialiser Odoo (obligatoire avant de manipuler l'ORM)
    odoo.tools.config['db_host'] = 'localhost'
    odoo.tools.config['db_name'] = cfg.db['name']
    odoo.tools.config['db_user'] = cfg.db['user']
    odoo.tools.config['db_password'] = cfg.db['password']
    odoo.tools.config['without_demo'] = True
    odoo.tools.config['log_level'] = 'info'
    odoo.tools.config['addons_path'] = f'{ODOO_PATH}/addons,{custom_addons}'

    # Charger les modules de base (corrige le bug "base_registry_signaling")
    server.load_server_wide_modules()

    # Charger l'environnement ORM
    registry = odoo.modules.registry.Registry(cfg.db['name'])

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        #create_oldodoo_adhpro(env)
        create_oldodoo_adh(env)

if __name__ == '__main__':
    main()
