import sys
import re
import os
import requests
import json
import config as cfg
import configsync as cfgs
from datetime import datetime

# --- CONFIGURATION à adapter ---
ODOO_PATH = '/opt/odoo18/odoo18'          # chemin vers dossier odoo (avec odoo/__init__.py)
custom_addons = '/opt/odoo18/odoo18/custom-addons'
#API_KEY = 'XXXX'
#OLD_ODOO_URL = "https://XXXX"
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

def create_cat(env):
    categories = get_categories()
    # Créer une étiquette CRM
    for cat in categories:
        print(cat[2])
        new_tag = env['res.partner.category'].create({
           'name': cat[2]
        })

# Récupère l'ancien id de la catégorie de l'adhérent à partir de l'ancien id de l'adhérent 
def get_cat_from_respartner(partnerid):
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getCatByPartner?partnerid='+str(partnerid), params={}, headers=headers, verify=False)
    results = json.loads(resp.text)
    return results

# Récupère le nom de la catégorie de l'adhérent à partir de l'ancien id de l'adhérent 
def get_cat_fromoldadh(oldpartnerid, allcat):
    catids = get_cat_from_respartner(oldpartnerid)
    if (len(catids)>0):
        for cat in allcat:
            if (cat[0] == catids[0][0]):
                print(cat[2])
                return cat[2]
    else:
        return False

# def create_invoice_adh(env, name, partner, price, invoice_date, state):
#     product = env['product.product'].search([('name', '=', 'Adh')], limit=1)

#     # Créer une facture simulant l’adhésion (si module "account" activé)
#     invoice = env['account.move'].create({
#         # a tester
#         'name': name,
#         'partner_id': partner.id,
#         'state': 'draft',
#         'move_type': 'out_invoice',
#         'invoice_date': invoice_date,
#         'invoice_line_ids': [(0, 0, {
#             'product_id': product.id,
#             'quantity': 1,
#             'price_unit': price,
#         })],
#     })

#     # Valider la facture (optionnel)
#     invoice.action_post()    
#     return invoice

def create_invoice(env, name, partner, price, invoice_date, state, invoicelines, payments):
    print("CREATE INVOICE")
    #invoice = ""
    invoice_lines = []
    for invoiceline in invoicelines:
        if (invoiceline[1] == "[Adh] Adh"):
            product = env['product.product'].search([('name', '=', 'Adh')], limit=1)
        else:
            product = env['product.product'].search([('name', '=', invoiceline[1])], limit=1)
        invoice_lines.append(
            (0, 0, {
                'product_id': product.id,
                'quantity': invoiceline[12],
                'price_unit': invoiceline[10],
            })
        )
    #print(invoice_lines)
    print()
    #product = env['product.product'].search([('name', '=', 'Contribution de développement')], limit=1)

    #Créer une facture 
    invoice = env['account.move'].create({
        'name': name,
        'partner_id': partner.id,
        'move_type': 'out_invoice',
        'invoice_date': invoice_date,
        'invoice_line_ids': invoice_lines
    })

    # Valider la facture (optionnel)
    invoice.action_post()

    if (state == "paid"):
        if (payments != None):
            for payment in payments:
                print(payment)
                journal_name = payment[28]
                payment_date = datetime.strptime(payment[14], "%a, %d %b %Y %H:%M:%S %Z")
                print(payment_date)
                amount = payment[12]
                print(amount)
                print(journal_name)
                # Chercher le bon journal
                if (journal_name == "Banque"):
                    journal = env['account.journal'].search([('name', '=', "Bank")], limit=1)
                else:
                    journal = env['account.journal'].search([('name', '=', journal_name)], limit=1)
                print(journal.id)
                # 3. Payer la facture
                payment_register = env['account.payment.register'].with_context(
                    active_model='account.move',
                    active_ids=invoice.ids,
                ).create({
                    'payment_date': payment_date,
                    'journal_id': journal.id,
                    'amount': amount
                })
                #print (payment_register)
                payment_register.action_create_payments()

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
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getMemberships?partner='+str(partnerid), params={}, headers=headers, verify=False)
    results = json.loads(resp.text)
    return results

def get_categories():
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getPartnerCat', params={}, headers=headers, verify=False)
    results = json.loads(resp.text)
    return results

def get_new_asso_id(env, email):
    filters2 = [('email', '=', email)]
    partners = env['res.partner'].search(filters2, limit=1)
    return partners.id

def create_oldodoo_adhpro(env, allcat):
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getAdhpros', params={}, headers=headers, verify=False)
    results = json.loads(resp.text)
    for result in results:
        infos = {
            'name': result['name'],
            'email': result['email'],
            'contact_email': result['email'],
            'phone': result['phone'],
            'account_cyclos': result['account_cyclos'],
            'street': result['street'],
            'zip': result['zip'],
            'city': result['city'],
            'is_company': 't',
            'prvlt_sepa': result['prvlt_sepa'],
            'is_organization': result['is_organization'],
            'detailed_activity': result['detailed_activity'],
            'comment': result['comment'],
            'currency_exchange_office': result['currency_exchange_office']
        }
        catname = get_cat_fromoldadh(result['id'], allcat)
        if (catname != False):
            cat = env['res.partner.category'].search([('name', '=', catname)], limit=1)
            infos['category_id'] = [(4, cat.id)]
        
        partner = create_adh(env, infos)
        create_invoices_for_adh(env, result['id'], partner)
        #invoic
        # 
        # memberships = get_memberships(result['id'])
        # for membership in memberships:
        #     date1 = datetime.strptime(membership[3], "%a, %d %b %Y %H:%M:%S %Z")
        #     date2 = datetime.strptime(membership[4], "%a, %d %b %Y %H:%M:%S %Z")
        #     number = membership[47]
        #     invoice = create_invoice_adh(env, number, partner, membership[7], date1, 'paid')
        #     membership = create_membership(env, partner, invoice, date1, date2)

def create_oldodoo_adh(env):
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getAssos', params={}, headers=headers, verify=False)
    resultassos = json.loads(resp.text)
    assos = {}
    defaultasso = ""
    for resultasso in resultassos:
        assos[resultasso['id']] = get_new_asso_id(env,resultasso['email'])
        if (resultasso['email'] == 'cyclos@florain.fr'):
            defaultasso = get_new_asso_id(env,resultasso['email'])
    #print(assos)

    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getAdhs', params={}, headers=headers, verify=False)
    resultadhs = json.loads(resp.text)
    for result in resultadhs:
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
            'comment': result['comment'],
            'changeeuros': result['changeeuros']
        }
        if (result['orga_choice'] in assos):
            infos['orga_choice'] = assos[result['orga_choice']]
        else:
            infos['orga_choice'] = defaultasso
        partner = create_adh(env, infos)
        create_invoices_for_adh(env, result['id'], partner)
        # memberships = get_memberships(result['id'])
        # for membership in memberships:
        #     date1 = datetime.strptime(membership[3], "%a, %d %b %Y %H:%M:%S %Z")
        #     date2 = datetime.strptime(membership[4], "%a, %d %b %Y %H:%M:%S %Z")          
        #     invoice = create_invoice_adh(env, partner, membership[7], date1)
        #     membership = create_membership(env, partner, invoice, date1, date2)

# def get_newid_from_mail(env, email):
#     filters2 = [('email', '=', email)]
#     partner = env['res.partner'].search(filters2, limit=1)
#     return partner

def get_old_adh():
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getAdhs', params={}, headers=headers, verify=False)
    resultadhs = json.loads(resp.text)
    return resultadhs

def get_old_adhpro():
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getAdhpros', params={}, headers=headers, verify=False)
    resultadhs = json.loads(resp.text)
    return resultadhs

def get_invoices(env, partnerid):
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getInvoices', params={'partnerid':partnerid}, headers=headers, verify=False)
    invoices = json.loads(resp.text)
    return invoices

def get_invoice_lines(env, invoiceid):
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getInvoiceLines', params={'invoiceid':invoiceid}, headers=headers, verify=False)
    invoicelines = json.loads(resp.text)
    return invoicelines

def get_invoice_payments(env, ref):
    headers = {'x-api-key': cfgs.oldapi['key'], 'Content-type': 'application/json', 'Accept': 'text/plain'}
    resp = requests.get(cfgs.oldapi['url']+'/getPayments', params={'ref':ref}, headers=headers, verify=False)
    payments = json.loads(resp.text)
    return payments

def create_invoices_for_adh(env, adhid, newpartner):
    invoices = get_invoices(env, adhid)
    for invoice in invoices:
        #print(adh['name'])
        invoicelines = get_invoice_lines(env, invoice[0])
            
        date1 = datetime.strptime(invoice[13], "%a, %d %b %Y %H:%M:%S %Z")
        date2 = datetime.strptime(invoice[14], "%a, %d %b %Y %H:%M:%S %Z")
        number = invoice[7]
        amount = invoice[24]
        state = invoice[11]
        if (state == "open"):
            state = "not_paid"
        ref = invoice[9]
        print(ref)
        if (ref != None):
            payments = get_invoice_payments(env, ref)
        else:
            payments = None
        print(state)
        print(number)
        # A adapter avec une nvelle fonction pour contribution de dev
        invoice = create_invoice(env, number, newpartner, amount, date1, state, invoicelines, payments)

# def sync_invoices(env):
#     adhs = get_old_adhpro()
#     for adh in adhs:
#         payments = []
#         #print("OLD ID : "+str(adh['id']))
#         #newpartner = get_newid_from_mail(env, adh['email'])
#         #print("NEW ID : "+str(newid))
#         invoices = get_invoices(env, adh['id'])
#         for invoice in invoices:
#             print(adh['name'])
#             invoicelines = get_invoice_lines(env, invoice[0])
            
#             date1 = datetime.strptime(invoice[13], "%a, %d %b %Y %H:%M:%S %Z")
#             date2 = datetime.strptime(invoice[14], "%a, %d %b %Y %H:%M:%S %Z")
#             number = invoice[7]
#             amount = invoice[24]
#             state = invoice[11]
#             if (state == "open"):
#                 state = "not_paid"
#             ref = invoice[9]
#             print(ref)
#             if (ref != None):
#                 payments = get_invoice_payments(env, ref)
#             print(state)
#             print(number)
#             # A adapter avec une nvelle fonction pour contribution de dev
#             invoice = create_invoice(env, number, newpartner, amount, date1, state, invoicelines, payments)
#     #results = json.loads(resp.text)
#     #for result in results:
        

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
        #create_oldodoo_adh(env)
        #sync_invoices(env)
        # First Step - create all Categories
        #create_cat(env)
        # Second Step - get All Categories
        allcat = get_categories()
        # Third Step - Create Adh pro
        #create_oldodoo_adhpro(env, allcat)
        # Fourth Step - Create adh part
        create_oldodoo_adh(env)
        # Fifth Step - Add contacts to adh pro

if __name__ == '__main__':
    main()
