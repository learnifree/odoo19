# -*- coding: utf-8 -*-
{
    'name': 'AMB CRM - Immigration & Education Consulting',
    'version': '1.0.0',
    'category': 'CRM',
    'summary': 'Complete CRM for immigration and education consulting firms',
    'description': """
AMB CRM Module
==============
Complete CRM solution for immigration and education consulting firms covering:
- Lead capture and management
- Opportunity pipeline management
- Assessment and eligibility evaluation
- Service proposals and fee management
- Payment tracking and invoicing
- Agreement and contract generation
    """,
    'author': 'AMB Solutions',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'crm',
        'sale',
        'account',
        'website',
        'portal',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data
        'data/sequence_data.xml',
        'data/email_templates.xml',
        # Views
        'views/lead_views.xml',
        'views/opportunity_views.xml',
        'views/assessment_views.xml',
        'views/assessment_wizard_views.xml',
        'views/payment_views.xml',
        'views/agreement_views.xml',
        'views/client_case_views.xml',
        'views/service_package_views.xml',
        'views/lead_convert_wizard_views.xml',
        'views/opportunity_convert_wizard_views.xml',
        'views/create_invoice_wizard_views.xml',
        'views/menu_views.xml',
        # Portal Templates (for contract signing)
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}