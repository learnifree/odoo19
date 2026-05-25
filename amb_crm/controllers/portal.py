# -*- coding: utf-8 -*-
"""
Portal Controller for AMB CRM Contract Signing

Allows customers to access and sign contracts via Odoo Client Portal.
"""

from odoo import fields, _
from odoo.http import request, route, Controller
from odoo.addons.portal.controllers.portal import CustomerPortal


class AmbContractPortal(CustomerPortal):
    """Portal controller for contract signing"""

    def _get_agreement_by_token(self, token):
        """
        Shared helper: look up a valid, signable agreement by access token.
        Returns (agreement, error_response) — one will always be None.
        """
        if not token or len(token) < 10:
            return None, request.redirect('/web/login?error=invalid_token')

        agreement = request.env['amb.agreement'].sudo().search([
            ('access_token', '=', token)
        ], limit=1)

        if not agreement:
            return None, request.redirect('/web/login?error=invalid_token')

        return agreement, None

    # ------------------------------------------------------------------ #
    #  GET  /amb/contract/sign/<token>   — render the signing page        #
    # ------------------------------------------------------------------ #
    @route(['/amb/contract/sign/<string:token>'],
           type='http', auth='public', website=True, methods=['GET'])
    def contract_sign_page(self, token, **kwargs):
        """Landing page for contract signing via token link from email."""
        agreement, err = self._get_agreement_by_token(token)
        if err:
            return err

        if agreement.state == 'signed' and agreement.signature_data:
            return request.render('amb_crm.contract_already_signed', {
                'agreement': agreement,
            })

        if agreement.state not in ('sent', 'partially_signed'):
            return request.render('amb_crm.contract_not_available', {
                'agreement': agreement,
            })

        # KEY FIX: The POST action also uses the token in the URL, not the
        # agreement_id.  This means the QWeb form never needs a hidden token
        # input field — the token travels in the URL the entire time.
        # Form action: POST /amb/contract/sign/<token>
        return request.render('amb_crm.contract_sign_page', {
            'agreement': agreement,
            'customer': agreement.partner_id,
            'token': token,
            # Convenience: build the form action URL here so the template
            # never has to construct it manually.
            'form_action': '/amb/contract/sign/%s' % token,
        })

    # ------------------------------------------------------------------ #
    #  POST /amb/contract/sign/<token>   — process submitted signature    #
    # ------------------------------------------------------------------ #
    # KEY FIX: POST to the SAME token URL as GET.
    # Previous version POSTed to /amb/contract/<id>/sign and expected a
    # hidden <input name="token"> in the form body.  When that input was
    # missing or stripped by a browser/CSP, token arrived as None →
    # the controller always returned invalid_token.
    # Using the token in the URL itself removes the hidden-field dependency
    # entirely and makes the flow robust.
    @route(['/amb/contract/sign/<string:token>'],
           type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def contract_sign_submit(self, token, signer_name=None, signature_data=None, **kwargs):
        """Handle signature submission — token comes from the URL, not POST body."""
        agreement, err = self._get_agreement_by_token(token)
        if err:
            return err

        if agreement.state == 'signed' and agreement.signature_data:
            return request.render('amb_crm.contract_already_signed', {
                'agreement': agreement,
            })

        if agreement.state not in ('sent', 'partially_signed'):
            return request.render('amb_crm.contract_not_available', {
                'agreement': agreement,
                'error': _('Contract is no longer available for signing.'),
            })

        if not signer_name:
            return request.render('amb_crm.contract_sign_page', {
                'agreement': agreement,
                'customer': agreement.partner_id,
                'token': token,
                'form_action': '/amb/contract/sign/%s' % token,
                'error': _('Please enter your name to sign.'),
            })

        if not signature_data:
            return request.render('amb_crm.contract_sign_page', {
                'agreement': agreement,
                'customer': agreement.partner_id,
                'token': token,
                'form_action': '/amb/contract/sign/%s' % token,
                'error': _('Please provide your signature.'),
            })

        # Signature data from a JS canvas pad arrives as a base64 data-URL:
        # "data:image/png;base64,iVBORw0K..."
        # Odoo Binary fields store only the raw base64 payload (no prefix).
        if isinstance(signature_data, str) and ',' in signature_data:
            signature_data = signature_data.split(',', 1)[1]
        # At this point signature_data is an ASCII base64 string — Odoo ORM
        # accepts str directly for Binary fields (it encodes internally).

        agreement.write({
            'signer_name': signer_name,
            'signer_email': agreement.partner_id.email,
            'signature_data': signature_data,
            'signature_date': fields.Datetime.now(),
            'state': 'signed',
        })

        agreement._notify_signature()

        return request.render('amb_crm.contract_signed_success', {
            'agreement': agreement,
        })

    # ------------------------------------------------------------------ #
    #  GET  /amb/contract/<token>/pdf    — download PDF (token in URL)    #
    # ------------------------------------------------------------------ #
    @route(['/amb/contract/<string:token>/pdf'],
           type='http', auth='public', website=True, methods=['GET'])
    def contract_download_pdf(self, token, **kwargs):
        """Download contract PDF — token in URL, no hidden field needed."""
        agreement, err = self._get_agreement_by_token(token)
        if err:
            return err

        pdf_content, _ = (
            request.env.ref('amb_crm.action_agreement_report')
            .sudo()
            .render_qweb_pdf([agreement.id])
        )

        return request.make_response(pdf_content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename=%s.pdf;' % agreement.name),
        ])


class AmbContractController(Controller):
    """JSON API endpoint for contract signing (used by JS/mobile clients)."""

    @route('/amb/api/contract/sign', type='json', auth='public', csrf=False)
    def api_sign_contract(self, token, signer_name, signature_data):
        """Sign a contract via JSON API. Token is passed explicitly in the payload."""
        if not token:
            return {'success': False, 'error': 'Token required'}

        agreement = request.env['amb.agreement'].sudo().search([
            ('access_token', '=', token)
        ], limit=1)

        if not agreement:
            return {'success': False, 'error': 'Invalid token'}

        if agreement.state not in ('sent', 'partially_signed'):
            return {'success': False, 'error': 'Contract not available for signing'}

        if isinstance(signature_data, str) and ',' in signature_data:
            signature_data = signature_data.split(',', 1)[1]

        agreement.write({
            'signer_name': signer_name,
            'signer_email': agreement.partner_id.email,
            'signature_data': signature_data,
            'signature_date': fields.Datetime.now(),
            'state': 'signed',
        })

        agreement._notify_signature()

        return {'success': True, 'agreement_id': agreement.id}
