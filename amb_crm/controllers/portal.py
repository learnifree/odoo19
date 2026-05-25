# -*- coding: utf-8 -*-
"""
Portal Controller for AMB CRM Contract Signing

Allows customers to access and sign contracts via Odoo Client Portal.
"""

from odoo import SUPERUSER_ID, fields, _
from odoo.http import request, route, Controller
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, ValidationError


class AmbContractPortal(CustomerPortal):
    """Portal controller for contract signing"""

    @route(['/amb/contract/sign/<string:token>'], type='http', auth='public', website=True)
    def contract_sign_page(self, token, **kwargs):
        """Landing page for contract signing via token"""
        # Validate token is not empty
        if not token or len(token) < 10:
            return request.redirect('/web/login?error=invalid_token')
        
        # Search agreement by access token
        agreement = request.env['amb.agreement'].sudo().search([
            ('access_token', '=', token)
        ], limit=1)
        
        if not agreement:
            return request.redirect('/web/login?error=invalid_token')
        
        # Check if already signed
        if agreement.state == 'signed' and agreement.signature_data:
            return request.render('amb_crm.contract_already_signed', {
                'agreement': agreement,
            })
        
        # Check if contract is sent for signing
        if agreement.state not in ('sent', 'partially_signed'):
            return request.render('amb_crm.contract_not_available', {
                'agreement': agreement,
            })
        
        # Render signing page
        return request.render('amb_crm.contract_sign_page', {
            'agreement': agreement,
            'customer': agreement.partner_id,
        })

    @route(['/amb/contract/<int:agreement_id>/sign'], type='http', auth='public', website=True)
    def contract_sign_submit(self, agreement_id, signer_name=None, signature_data=None, **kwargs):
        """Handle signature submission from portal"""
        # Get agreement
        agreement = request.env['amb.agreement'].sudo().browse(agreement_id)
        
        if not agreement.exists():
            return request.redirect('/web/login?error=invalid_agreement')
        
        # Validate state
        if agreement.state not in ('sent', 'partially_signed'):
            return request.render('amb_crm.contract_not_available', {
                'agreement': agreement,
                'error': 'Contract is no longer available for signing.',
            })
        
        # Validate required fields
        if not signer_name:
            return request.render('amb_crm.contract_sign_page', {
                'agreement': agreement,
                'customer': agreement.partner_id,
                'error': 'Please enter your name to sign.',
            })
        
        if not signature_data:
            return request.render('amb_crm.contract_sign_page', {
                'agreement': agreement,
                'customer': agreement.partner_id,
                'error': 'Please provide your signature.',
            })
        
        # Update agreement with signature
        agreement.write({
            'signer_name': signer_name,
            'signer_email': agreement.partner_id.email,
            'signature_data': signature_data.encode('utf-8') if isinstance(signature_data, str) else signature_data,
            'signature_date': fields.Datetime.now(),
            'state': 'signed',
        })
        
        # Send notification to company
        agreement._notify_signature()
        
        return request.render('amb_crm.contract_signed_success', {
            'agreement': agreement,
        })

    @route(['/amb/contract/<int:agreement_id>/pdf'], type='http', auth='public', website=True)
    def contract_download_pdf(self, agreement_id, **kwargs):
        """Download contract PDF"""
        agreement = request.env['amb.agreement'].sudo().browse(agreement_id)
        
        if not agreement.exists():
            return request.redirect('/web/login?error=invalid_agreement')
        
        # Check access
        if not agreement.access_token and request.env.user.id == request.env.ref('base.public_user').id:
            return request.redirect('/web/login')
        
        # Generate PDF report
        pdf_content, _ = request.env.ref('amb_crm.action_agreement_report').sudo().render_qweb_pdf([agreement.id])
        
        pdf_http_headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename=%s.pdf;' % agreement.name),
        ]
        
        return request.make_response(pdf_content, headers=pdf_http_headers)


class AmbContractController(Controller):
    """HTTP Controller for contract signing API"""

    @route('/amb/api/contract/sign', type='json', auth='public', csrf=False)
    def api_sign_contract(self, token, signer_name, signature_data):
        """JSON API endpoint for contract signing"""
        # Verify token
        agreement = request.env['amb.agreement'].sudo().search([
            ('access_token', '=', token)
        ], limit=1)
        
        if not agreement:
            return {'success': False, 'error': 'Invalid token'}
        
        if agreement.state not in ('sent', 'partially_signed'):
            return {'success': False, 'error': 'Contract not available for signing'}
        
        # Save signature
        agreement.write({
            'signer_name': signer_name,
            'signer_email': agreement.partner_id.email,
            'signature_data': signature_data,
            'signature_date': fields.Datetime.now(),
            'state': 'signed',
        })
        
        # Notify company
        agreement._notify_signature()
        
        return {'success': True, 'agreement_id': agreement.id}