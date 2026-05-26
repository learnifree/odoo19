# -*- coding: utf-8 -*-
"""
Portal Controller for AMB CRM - Agreement Signing

Implements the Odoo-standard client portal pattern for agreements:
  - /my/agreements          → list all agreements for the logged-in partner
  - /my/agreements/<id>     → view & sign a specific agreement
                              (auth='public' so access_token links from email work)
  - POST /my/agreements/<id>/sign  → submit signature

The email sent by action_send_for_signing() links to:
  /my/agreements/<id>?access_token=<token>

This mirrors how Odoo's account module handles invoices at /my/invoices.
"""

from odoo import fields, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class AmbAgreementPortal(CustomerPortal):
    """Portal controller for AMB agreements — follows the /my/invoices pattern."""

    # ------------------------------------------------------------------
    # Portal home counter
    # ------------------------------------------------------------------

    def _prepare_home_portal_values(self, counters):
        """Add agreement count to the portal home dashboard."""
        values = super()._prepare_home_portal_values(counters)
        if 'agreement_count' in counters:
            AgreementSudo = request.env['amb.agreement'].sudo()
            partner = request.env.user.partner_id
            agreement_count = AgreementSudo.search_count([
                ('partner_id', '=', partner.id),
                ('state', 'not in', ('draft', 'cancelled')),
            ])
            values['agreement_count'] = agreement_count
        return values

    # ------------------------------------------------------------------
    # /my/agreements  — list
    # ------------------------------------------------------------------

    @route(['/my/agreements', '/my/agreements/page/<int:page>'],
           type='http', auth='user', website=True, readonly=True)
    def portal_my_agreements(self, page=1, sortby=None, **kw):
        """List all agreements belonging to the logged-in partner."""
        partner = request.env.user.partner_id
        AgreementSudo = request.env['amb.agreement'].sudo()

        domain = [
            ('partner_id', '=', partner.id),
            ('state', 'not in', ('draft', 'cancelled')),
        ]

        sortings = {
            'date':  {'label': _('Newest'),    'order': 'create_date desc'},
            'name':  {'label': _('Reference'), 'order': 'name asc'},
            'state': {'label': _('Status'),    'order': 'state asc'},
        }
        sortby = sortby or 'date'
        order = sortings.get(sortby, sortings['date'])['order']

        total = AgreementSudo.search_count(domain)
        pager = portal_pager(
            url='/my/agreements',
            url_args={'sortby': sortby},
            total=total,
            page=page,
            step=self._items_per_page,
        )

        agreements = AgreementSudo.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset'],
        )
        request.session['my_agreements_history'] = agreements.ids[:100]

        return request.render('amb_crm.portal_my_agreements', {
            'agreements': agreements,
            'page_name': 'agreement',
            'pager': pager,
            'sortings': sortings,
            'sortby': sortby,
            'default_url': '/my/agreements',
        })

    # ------------------------------------------------------------------
    # /my/agreements/<id>  — detail / signing page
    # ------------------------------------------------------------------

    @route(['/my/agreements/<int:agreement_id>'],
           type='http', auth='public', website=True, methods=['GET'])
    def portal_agreement_detail(self, agreement_id, access_token=None, **kw):
        """
        Show the agreement detail / signing page.

        auth='public' so that the token link from the email works even before
        the client has logged in.  _document_check_access() handles both cases:
          - logged-in portal user who owns the record
          - anonymous visitor with a valid access_token query param
        """
        try:
            agreement = self._document_check_access(
                'amb.agreement', agreement_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/web/login?redirect=/my/agreements/%d' % agreement_id)

        if agreement.state == 'signed' and agreement.signature_data:
            return request.render('amb_crm.contract_already_signed', {
                'agreement': agreement,
            })

        if agreement.state not in ('sent', 'partially_signed'):
            return request.render('amb_crm.contract_not_available', {
                'agreement': agreement,
            })

        # Build the POST URL — token stays in the query string so the POST
        # handler can also call _document_check_access() without a hidden field.
        if access_token:
            form_action = '/my/agreements/%d/sign?access_token=%s' % (agreement_id, access_token)
        else:
            form_action = '/my/agreements/%d/sign' % agreement_id

        return request.render('amb_crm.contract_sign_page', {
            'agreement': agreement,
            'customer': agreement.partner_id,
            'access_token': access_token,
            'form_action': form_action,
        })

    # ------------------------------------------------------------------
    # POST /my/agreements/<id>/sign  — submit signature
    # ------------------------------------------------------------------

    @route(['/my/agreements/<int:agreement_id>/sign'],
           type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def portal_agreement_sign(self, agreement_id, access_token=None,
                              signer_name=None, signature_data=None, **kw):
        """
        Process the submitted signature.

        Token travels as a query-string param on the POST URL so it is never
        dependent on a hidden form field that could be stripped by a browser
        or CSP policy.
        """
        try:
            agreement = self._document_check_access(
                'amb.agreement', agreement_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/web/login?redirect=/my/agreements/%d' % agreement_id)

        if agreement.state == 'signed' and agreement.signature_data:
            return request.render('amb_crm.contract_already_signed', {
                'agreement': agreement,
            })

        if agreement.state not in ('sent', 'partially_signed'):
            return request.render('amb_crm.contract_not_available', {
                'agreement': agreement,
                'error': _('This agreement is no longer available for signing.'),
            })

        # Build form_action for re-render on validation errors
        if access_token:
            form_action = '/my/agreements/%d/sign?access_token=%s' % (agreement_id, access_token)
        else:
            form_action = '/my/agreements/%d/sign' % agreement_id

        if not signer_name:
            return request.render('amb_crm.contract_sign_page', {
                'agreement': agreement,
                'customer': agreement.partner_id,
                'access_token': access_token,
                'form_action': form_action,
                'error': _('Please enter your full name to sign.'),
            })

        if not signature_data:
            return request.render('amb_crm.contract_sign_page', {
                'agreement': agreement,
                'customer': agreement.partner_id,
                'access_token': access_token,
                'form_action': form_action,
                'error': _('Please draw your signature before submitting.'),
            })

        # Strip the data-URL prefix that the canvas toDataURL() adds:
        # "data:image/png;base64,iVBORw0K..." → "iVBORw0K..."
        if isinstance(signature_data, str) and ',' in signature_data:
            signature_data = signature_data.split(',', 1)[1]

        agreement.sudo().write({
            'signer_name': signer_name,
            'signer_email': agreement.partner_id.email,
            'signature_data': signature_data,
            'signature_date': fields.Datetime.now(),
            'state': 'signed',
        })

        agreement.sudo()._notify_signature()

        return request.render('amb_crm.contract_signed_success', {
            'agreement': agreement,
        })

    # ------------------------------------------------------------------
    # /my/agreements/<id>/pdf  — download PDF
    # ------------------------------------------------------------------

    @route(['/my/agreements/<int:agreement_id>/pdf'],
           type='http', auth='public', website=True, methods=['GET'])
    def portal_agreement_pdf(self, agreement_id, access_token=None, **kw):
        """Download the agreement as a PDF."""
        try:
            agreement = self._document_check_access(
                'amb.agreement', agreement_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect('/web/login?redirect=/my/agreements/%d' % agreement_id)

        pdf_content, _ = (
            request.env.ref('amb_crm.action_agreement_report')
            .sudo()
            .render_qweb_pdf([agreement.id])
        )

        return request.make_response(pdf_content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename="%s.pdf"' % agreement.name),
        ])
