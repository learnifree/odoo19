# -*- coding: utf-8 -*-
"""
Agreement Model for AMB CRM

Handles contract/agreement generation and e-signature support.
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AmbAgreement(models.Model):
    """Agreement Model - Contract Generation"""
    _name = 'amb.agreement'
    _description = 'AMB Agreement'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    # Reference
    name = fields.Char(
        string='Agreement Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    # Opportunity Link
    opportunity_id = fields.Many2one(
        'amb.opportunity',
        string='Opportunity',
        tracking=True,
    )

    # Client Case Link (after conversion)
    case_id = fields.Many2one(
        'amb.client.case',
        string='Client Case',
        readonly=True,
    )

    # Payment Link - Contract can only be generated when payment is 'paid'
    payment_id = fields.Many2one(
        'amb.payment',
        string='Payment',
        tracking=True,
    )

    # Assessment Link (for program type info)
    assessment_id = fields.Many2one(
        'amb.assessment',
        string='Assessment',
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='opportunity_id.partner_id',
        store=True,
    )

    # Program Type (for template selection)
    program_type = fields.Many2one(
        'product.product',
        string='Program Type',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
    )

    # Template
    template_id = fields.Many2one(
        'amb.agreement.template',
        string='Agreement Template',
        tracking=True,
    )

    # Agreement Type
    agreement_type = fields.Selection([
        ('retainer', 'Retainer Agreement'),
        ('service', 'Service Agreement'),
        ('consulting', 'Consulting Agreement'),
        ('study_visa', 'Study Visa Agreement'),
        ('work_permit', 'Work Permit Agreement'),
        ('immigration', 'Immigration Agreement'),
        ('other', 'Other'),
    ], string='Agreement Type', required=True, tracking=True)

    # Contract Details
    service_scope = fields.Text(string='Service Scope')
    start_date = fields.Date(
        string='Start Date',
        default=fields.Date.context_today,
    )

    end_date = fields.Date(string='End Date')

    # Fee Reference
    total_fee = fields.Monetary(
        string='Total Fee',
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
    )

    # Contract Content
    body_html = fields.Html(
        string='Contract Content',
        required=True,
        sanitize=False,
    )

    # E-Signature Fields
    # NOTE: portal.mixin already provides access_token — we do NOT redefine it here.
    # Redefining it caused a field conflict that broke _portal_ensure_token() and
    # made the portal URL resolve to '#' instead of /my/agreements/<id>.
    # Token generation is handled via _portal_ensure_token() in generate_access_token().

    signature_data = fields.Binary(
        string='Customer Signature',
        attachment=True,
    )

    signature_date = fields.Datetime(
        string='Signature Date',
        readonly=True,
    )

    signer_name = fields.Char(string='Signer Name')
    signer_email = fields.Char(string='Signer Email')

    # Consultant Signature
    consultant_signature_data = fields.Binary(
        string='Consultant Signature',
        attachment=True,
    )

    consultant_signature_date = fields.Datetime(
        string='Consultant Signature Date',
        readonly=True,
    )

    consultant_signatory = fields.Many2one(
        'res.users',
        string='Consultant Signatory',
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent for Signing'),
        ('partially_signed', 'Partially Signed'),
        ('signed', 'Fully Signed'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True, copy=False, index=True)

    # Signed Document
    signed_document = fields.Binary(
        string='Signed Document',
        attachment=True,
    )

    document_name = fields.Char(string='Document Name')

    # Notes
    notes = fields.Text(string='Notes')
    terms_conditions = fields.Html(string='Terms & Conditions')

    # Assignment
    user_id = fields.Many2one(
        'res.users',
        string='Prepared By',
        default=lambda self: self.env.user,
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(string='Active', default=True)

    # Attachment
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
    )

    @api.model
    def create(self, vals_list):
        """Generate sequence for new agreements"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amb.agreement') or 'New'

            # Initialize body_html from template if not provided
            if not vals.get('body_html') and vals.get('template_id'):
                template = self.env['amb.agreement.template'].browse(vals['template_id'])
                if template.exists():
                    vals['body_html'] = template.body_html

            # Set default placeholder if still no body_html
            if not vals.get('body_html'):
                vals['body_html'] = '<p>Agreement content pending...</p>'

        return super().create(vals_list)

    def _compute_access_url(self):
        """Override portal.mixin to return the correct portal URL for agreements.

        This makes portal.mixin's _get_share_url() and get_portal_url() build
        links to /my/agreements/<id> instead of the default '#'.

        No @api.depends decorator needed: access_url is a non-stored computed
        field, so Odoo recomputes it on every read — always returning the
        correct /my/agreements/<id> URL.
        Note: @api.depends('id') is explicitly forbidden in Odoo 19
        (raises NotImplementedError).
        """
        for agreement in self:
            agreement.access_url = '/my/agreements/%s' % agreement.id

    def generate_access_token(self):
        """Generate / refresh the portal access token for signing.

        Uses portal.mixin._portal_ensure_token() so the token is always
        stored in the standard access_token field and is compatible with
        Odoo's _document_check_access() helper used in the portal controller.

        Both the write() and _portal_ensure_token() are called with sudo()
        so the token is always saved regardless of the calling user's access
        rights on the access_token field.
        """
        for agreement in self:
            # Force a fresh token every time 'Send Agreement' is called so
            # old email links are invalidated.
            # Use False (not '') so _portal_ensure_token()'s `if not self.access_token`
            # check reliably triggers a new token write.
            agreement.sudo().write({'access_token': False})
            agreement.sudo()._portal_ensure_token()

    # === Action Methods ===

    def action_send_for_signing(self):
        """Send agreement for signing via portal"""
        for agreement in self:
            agreement.generate_access_token()
            agreement.write({'state': 'sent'})

            template = self.env.ref('amb_crm.email_template_agreement_signing', raise_if_not_found=False)
            if template:
                template.send_mail(agreement.id, force_send=True)
            else:
                # Fallback chatter note when email template is missing
                portal_url = '%s/my/agreements/%s?access_token=%s' % (
                    agreement.get_base_url(), agreement.id, agreement.access_token
                )
                agreement.message_post(
                    body=_('Agreement sent for signing. Customer portal link: %s') % portal_url,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

    def action_sign(self):
        """Sign the agreement (placeholder for portal signing)"""
        self.ensure_one()
        if self.state not in ('sent', 'partially_signed'):
            raise ValidationError(_('Agreement must be sent for signing first'))

        self.write({
            'state': 'signed',
            'signature_date': fields.Datetime.now(),
        })

    def action_mark_active(self):
        """Mark agreement as active"""
        for agreement in self:
            agreement.write({'state': 'active'})

    def action_terminate(self):
        """Terminate the agreement"""
        for agreement in self:
            agreement.write({'state': 'terminated'})

    def action_cancel(self):
        """Cancel the agreement"""
        for agreement in self:
            agreement.write({'state': 'cancelled'})

    def action_print_agreement(self):
        """Print agreement PDF"""
        self.ensure_one()
        return self.env.ref('amb_crm.action_agreement_report').report_action(self)

    def action_download_signed(self):
        """Download signed document"""
        self.ensure_one()
        if not self.signed_document:
            raise ValidationError(_('No signed document available'))

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=amb.agreement&id=%d&field=signed_document&filename=%s' % (
                self.id, self.document_name or 'signed_agreement.pdf'
            ),
            'target': 'self',
        }

    @api.onchange('template_id')
    def _onchange_template(self):
        """Load content from template"""
        if self.template_id:
            self.body_html = self.template_id.body_html
            self.agreement_type = self.template_id.agreement_type
            self.terms_conditions = self.template_id.terms_conditions

    def update_body_from_template(self):
        """Update body from template"""
        for agreement in self:
            if agreement.template_id and agreement.template_id.body_html:
                agreement.body_html = agreement.template_id.body_html

    def map_fields(self):
        """Map customer fields into contract content"""
        for agreement in self:
            if not agreement.partner_id:
                continue

            partner = agreement.partner_id

            replacements = {
                '[[customer_name]]': partner.name or '',
                '[[customer_email]]': partner.email or '',
                '[[customer_phone]]': partner.phone or '',
                '[[customer_address]]': partner.street or '',
                '[[sign_date]]': fields.Date.today().strftime('%B %d, %Y'),
                '[[agreement_date]]': agreement.start_date.strftime('%B %d, %Y') if agreement.start_date else '',
                '[[service_scope]]': agreement.service_scope or '',
                '[[total_fee]]': str(agreement.total_fee) if agreement.total_fee else '',
                '[[program_type]]': agreement.program_type.name if agreement.program_type else '',
            }

            body = agreement.body_html
            for placeholder, value in replacements.items():
                body = body.replace(placeholder, str(value))

            agreement.body_html = body

    def _notify_signature(self):
        """Send notification when contract is signed"""
        for agreement in self:
            template = self.env.ref('amb_crm.email_template_contract_signed', raise_if_not_found=False)
            if template:
                template.send_mail(agreement.id, force_send=True)
            else:
                # FIX: _() was used without being imported — now imported at top of file
                agreement.message_post(
                    body=_('Contract signed by %s on %s') % (
                        agreement.signer_name or 'Customer',
                        agreement.signature_date or fields.Datetime.now()
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )


class AmbAgreementTemplate(models.Model):
    """Agreement Template Model"""
    _name = 'amb.agreement.template'
    _description = 'AMB Agreement Template'
    _order = 'name asc'

    name = fields.Char(
        string='Template Name',
        required=True,
    )

    agreement_type = fields.Selection([
        ('retainer', 'Retainer Agreement'),
        ('service', 'Service Agreement'),
        ('consulting', 'Consulting Agreement'),
        ('study_visa', 'Study Visa Agreement'),
        ('work_permit', 'Work Permit Agreement'),
        ('immigration', 'Immigration Agreement'),
        ('other', 'Other'),
    ], string='Agreement Type', required=True)

    program_type = fields.Many2one(
        'product.product',
        string='Program Type',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
        help='Auto-assign this template when generating contract for this program type',
    )

    body_html = fields.Html(
        string='Template Content',
        required=True,
        sanitize=False,
    )

    terms_conditions = fields.Html(string='Terms & Conditions')

    active = fields.Boolean(string='Active', default=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count',
        store=True,
    )

    @api.depends()
    def _compute_usage_count(self):
        for rec in self:
            rec.usage_count = self.env['amb.agreement'].search_count([
                ('template_id', '=', rec.id)
            ])
