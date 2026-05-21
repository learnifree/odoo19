# -*- coding: utf-8 -*-
"""
Payment Model for AMB CRM

Handles payment tracking and receipt generation.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbPayment(models.Model):
    """Payment Model - Payment Tracking"""
    _name = 'amb.payment'
    _description = 'AMB Payment'
    _order = 'payment_date desc, create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Reference
    name = fields.Char(
        string='Payment Reference',
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

    # Assessment Link
    assessment_id = fields.Many2one(
        'amb.assessment',
        string='Assessment',
        tracking=True,
    )

    # Program Type (from assessment's program_type)
    program_type = fields.Many2one(
        'product.product',
        string='Program Type',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
        tracking=True,
    )

    # Invoice Link (Odoo account.move)
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True,
        copy=False,
    )

    invoice_number = fields.Char(
        string='Invoice Number',
        related='invoice_id.name',
        readonly=True,
    )

    invoice_state = fields.Selection(
        string='Invoice Status',
        related='invoice_id.state',
        readonly=True,
    )

    # ===== NEW: Invoice Integration Fields =====
    
    # Invoice Amount Fields
    invoice_amount = fields.Monetary(
        string='Invoice Total',
        currency_field='currency_id',
        compute='_compute_invoice_fields',
        readonly=True,
    )
    
    invoice_paid_amount = fields.Monetary(
        string='Amount Paid',
        currency_field='currency_id',
        compute='_compute_invoice_fields',
        readonly=True,
    )
    
    invoice_outstanding_balance = fields.Monetary(
        string='Outstanding Balance',
        currency_field='currency_id',
        compute='_compute_invoice_fields',
        readonly=True,
    )
    
    # Invoice Date Fields
    invoice_date = fields.Date(
        string='Invoice Date',
        related='invoice_id.invoice_date',
        readonly=True,
    )
    
    invoice_due_date = fields.Date(
        string='Due Date',
        related='invoice_id.invoice_date_due',
        readonly=True,
    )
    
    # Invoice Status Fields
    invoice_payment_state = fields.Selection(
        string='Payment Status',
        selection=[
            ('not_paid', 'Not Paid'),
            ('in_payment', 'In Payment'),
            ('paid', 'Paid'),
            ('partial', 'Partially Paid'),
            ('reversed', 'Reversed'),
            ('blocked', 'Blocked'),
        ],
        compute='_compute_invoice_fields',
        readonly=True,
        store=True,
    )
    
    # Computed field to check if invoice is overdue
    invoice_overdue = fields.Boolean(
        string='Invoice Overdue',
        compute='_compute_invoice_overdue',
        readonly=True,
        store=True,
    )

    # Odoo Payment Link (account.payment)
    account_payment_id = fields.Many2one(
        'account.payment',
        string='Odoo Payment',
        readonly=True,
        copy=False,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
    )

    # Payment Details
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
        tracking=True,
    )

    expected_amount = fields.Monetary(
        string='Expected Amount',
        currency_field='currency_id',
    )

    # Payment Date
    payment_date = fields.Date(
        string='Payment Date',
        default=fields.Date.context_today,
        tracking=True,
    )

    due_date = fields.Date(string='Due Date')

    # Payment Method
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ], string='Payment Method', tracking=True)

    transaction_reference = fields.Char(string='Transaction Reference')
    bank_reference = fields.Char(string='Bank Reference')

    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ], string='State', default='pending', tracking=True, copy=False, index=True)

    # Receipt
    receipt_number = fields.Char(string='Receipt Number', copy=False)
    receipt_date = fields.Date(string='Receipt Date', copy=False)

    # Installment Info
    installment_number = fields.Integer(string='Installment #')
    total_installments = fields.Integer(string='Total Installments')

    # Notes
    notes = fields.Text(string='Notes')
    internal_notes = fields.Text(string='Internal Notes')

    # Attachment
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
    )

    # Assignment
    user_id = fields.Many2one(
        'res.users',
        string='Recorded By',
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

    # Computed
    remaining_amount = fields.Monetary(
        string='Remaining',
        currency_field='currency_id',
        compute='_compute_remaining',
    )

    is_overdue = fields.Boolean(
        string='Is Overdue',
        compute='_compute_is_overdue',
        store=True,
    )

    @api.depends('expected_amount', 'amount', 'state')
    def _compute_remaining(self):
        for rec in self:
            if rec.state == 'paid':
                rec.remaining_amount = 0
            else:
                rec.remaining_amount = (rec.expected_amount or 0) - rec.amount

    @api.depends('due_date', 'state')
    def _compute_is_overdue(self):
        for rec in self:
            rec.is_overdue = (
                rec.due_date and 
                rec.due_date < fields.Date.today() and 
                rec.state not in ('paid', 'cancelled', 'refunded')
            )

    @api.depends('invoice_id', 'invoice_id.amount_total', 'invoice_id.amount_residual', 'invoice_id.payment_state')
    def _compute_invoice_fields(self):
        """Compute invoice-related fields from linked account.move"""
        for rec in self:
            if rec.invoice_id:
                rec.invoice_amount = rec.invoice_id.amount_total
                rec.invoice_outstanding_balance = rec.invoice_id.amount_residual
                rec.invoice_paid_amount = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
                rec.invoice_payment_state = rec.invoice_id.payment_state
            else:
                rec.invoice_amount = 0
                rec.invoice_outstanding_balance = 0
                rec.invoice_paid_amount = 0
                rec.invoice_payment_state = 'not_paid'

    @api.depends('invoice_id', 'invoice_id.invoice_date_due', 'invoice_id.payment_state', 'invoice_id.state')
    def _compute_invoice_overdue(self):
        """Check if the linked invoice is overdue"""
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == 'posted':
                rec.invoice_overdue = (
                    rec.invoice_id.invoice_date_due and 
                    rec.invoice_id.invoice_date_due < fields.Date.today() and
                    rec.invoice_id.payment_state not in ('paid', 'reversed')
                )
            else:
                rec.invoice_overdue = False

    # Override write to auto-sync payment state with invoice status
    def write(self, vals):
        """Auto-sync payment state based on invoice payment status"""
        res = super().write(vals)
        
        # Auto-update payment state when invoice is linked or modified
        for payment in self:
            if payment.invoice_id and payment.invoice_id.payment_state:
                invoice_state = payment.invoice_id.payment_state
                
                # Map Odoo payment states to amb.payment states
                state_mapping = {
                    'paid': 'paid',
                    'in_payment': 'partial',
                    'partial': 'partial',
                }
                
                # Only auto-update if payment state is pending/partial and invoice is paid/partial
                if payment.state in ('pending', 'partial') and invoice_state in state_mapping:
                    # Check if amount matches - if fully paid, set to paid
                    if invoice_state == 'paid' or payment.invoice_outstanding_balance <= 0:
                        payment.write({'state': 'paid'})
                    elif invoice_state in ('in_payment', 'partial'):
                        payment.write({'state': 'partial'})
        
        return res

    @api.model
    @api.model
    def create(self, vals_list):
        """Generate sequence for new payments"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amb.payment') or 'New'
        
        return super().create(vals_list)

    # === Action Methods ===

    def action_create_invoice(self):
        """Open wizard to create invoice with customizable pricing"""
        self.ensure_one()
        
        # Check if program_type or assessment exists
        if not self.program_type and not self.assessment_id:
            raise ValidationError('Please select an Assessment or Program Type before creating an invoice.')
        
        # If invoice already exists, open it
        if self.invoice_id:
            return {
                'name': ('Invoice'),
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'type': 'ir.actions.act_window',
            }
        
        # Open the invoice creation wizard
        return {
            'name': ('Create Invoice'),
            'view_mode': 'form',
            'res_model': 'amb.create.invoice.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_payment_id': self.id,
            },
        }

    def action_create_invoice_direct(self):
        """Create Odoo invoice directly (original logic)"""
        self.ensure_one()
        
        # Check if program_type or assessment exists
        if not self.program_type and not self.assessment_id:
            raise ValidationError('Please select an Assessment or Program Type before creating an invoice.')
        
        if not self.invoice_id:
            # Get journal (default sales journal)
            journal_id = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            
            if not journal_id:
                raise ValidationError('Please configure a Sales Journal in Accounting.')
            
            # Determine the source assessment - either direct or through program_type
            source_assessment = self.assessment_id
            if not source_assessment and self.program_type:
                # Try to find the assessment that has this program_type
                source_assessment = self.env['amb.assessment'].search([
                    ('program_type', '=', self.program_type.id),
                    ('partner_id', '=', self.partner_id.id),
                ], limit=1, order='create_date desc')
            
            # Get product from program_type
            product_id = False
            service_name = 'Service Fee'
            price_unit = self.expected_amount or self.amount
            
            # Priority 1: Check if there's an assessment with program_type
            if source_assessment and source_assessment.program_type:
                product_id = source_assessment.program_type
                service_name = '%s - %s' % (
                    source_assessment.name or 'Assessment Service',
                    product_id.name or 'Immigration Service'
                )
                # Use assessment's program_type list_price, or payment expected_amount if available
                price_unit = self.expected_amount or product_id.list_price or price_unit
            
            # Priority 2: Check program_type directly on payment
            if not product_id and self.program_type:
                product_id = self.program_type
                service_name = self.program_type.name or 'Immigration Service'
                price_unit = self.expected_amount or self.program_type.list_price or price_unit
            
            # Last fallback: search for any product with immigration category
            if not product_id:
                immigration_product = self.env['product.product'].search([
                    ('categ_id.name', 'ilike', 'immigration'),
                ], limit=1)
                if immigration_product:
                    product_id = immigration_product
                    service_name = 'Immigration Service Fee'
                    price_unit = immigration_product.list_price or price_unit
            
            if not product_id:
                # Create a generic product line
                product_id = self.env.ref('product.product_product_1', raise_if_not_found=False)
            
            # Get the revenue account - use product's income account first, then journal default
            revenue_account_id = False
            if product_id:
                revenue_account_id = product_id.property_account_income_id.id
            if not revenue_account_id:
                # Fallback to journal's default account
                revenue_account_id = journal_id.default_account_id.id
            
            # Create invoice lines
            invoice_line_vals = []
            if product_id:
                invoice_line_vals.append((0, 0, {
                    'product_id': product_id.id,
                    'name': service_name,
                    'quantity': 1,
                    'price_unit': price_unit,
                    'account_id': revenue_account_id,
                }))
            
            # Build the invoice origin reference
            origin_ref = 'Payment: %s' % self.name
            if source_assessment:
                origin_ref += ' | Assessment: %s' % source_assessment.name
            
            # Create invoice
            invoice_vals = {
                'partner_id': self.partner_id.id,
                'move_type': 'out_invoice',
                'journal_id': journal_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': invoice_line_vals,
                'invoice_origin': origin_ref,
                'ref': origin_ref,
            }
            
            invoice = self.env['account.move'].create(invoice_vals)
            self.write({'invoice_id': invoice.id})
            
            # Return action to open the invoice
            return {
                'name': ('Invoice'),
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': invoice.id,
                'type': 'ir.actions.act_window',
            }
        
        # If invoice exists, open it
        return {
            'name': ('Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_mark_paid(self):
        """Mark payment as paid - auto-syncs invoice status"""
        for payment in self:
            if payment.state in ('pending', 'partial', 'overdue'):
                # Check if invoice exists
                if not payment.invoice_id:
                    raise ValidationError(
                        'Please create an Invoice first before marking this payment as Paid.'
                    )
                
                # Auto-create and post Odoo payment if not exists
                if not payment.account_payment_id:
                    payment.action_record_odoo_payment()
            
            payment.write({
                'state': 'paid',
            })

    def action_mark_partial(self):
        """Mark payment as partially paid"""
        for payment in self:
            payment.write({'state': 'partial'})

    def action_cancel(self):
        """Cancel payment"""
        for payment in self:
            payment.write({'state': 'cancelled'})

    def action_refund(self):
        """Mark payment as refunded"""
        for payment in self:
            payment.write({'state': 'refunded'})

    def action_record_odoo_payment(self):
        """Record Odoo payment and link it"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise ValidationError('Please create an Invoice first before recording payment.')
        
        if not self.account_payment_id:
            # Get payment method
            payment_method_id = self.env.ref('account.account_payment_method_manual_in', raise_if_not_found=False)
            
            # Create Odoo account.payment
            # Only use required fields to avoid field name issues
            payment_vals = {
                'partner_id': self.partner_id.id,
                'amount': self.amount,
                'date': self.payment_date or fields.Date.today(),
                'journal_id': self.env['account.journal'].search([
                    ('type', 'in', ['bank', 'cash']),
                    ('company_id', '=', self.company_id.id),
                ], limit=1).id,
            }
            
            # Try to add payment method if available
            if payment_method_id:
                payment_vals['payment_method_id'] = payment_method_id.id
            
            account_payment = self.env['account.payment'].create(payment_vals)
            account_payment.action_post()  # Post the payment
            
            self.write({'account_payment_id': account_payment.id})
            
            return {
                'name': ('Odoo Payment'),
                'view_mode': 'form',
                'res_model': 'account.payment',
                'res_id': account_payment.id,
                'type': 'ir.actions.act_window',
            }
        
        return {
            'name': ('Odoo Payment'),
            'view_mode': 'form',
            'res_model': 'account.payment',
            'res_id': self.account_payment_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_generate_receipt(self):
        """Generate payment receipt"""
        self.ensure_one()
        if not self.receipt_number:
            self.write({
                'receipt_number': self.env['ir.sequence'].next_by_code('amb.payment.receipt'),
                'receipt_date': fields.Date.today(),
            })
        return self.env.ref('amb_crm.action_payment_receipt').report_action(self)

    def action_generate_contract(self):
        """Generate contract/agreement for this payment - ONLY if payment state is 'paid'"""
        self.ensure_one()
        
        # Validate: Payment must be 'paid' before generating contract
        if self.state != 'paid':
            raise ValidationError(
                'Contract can only be generated when payment status is "Paid". '
                'Current status: %s. Please ensure payment is fully paid before generating contract.' % dict(self._fields['state'].selection).get(self.state, self.state)
            )
        
        # Check if contract already exists
        existing_agreement = self.env['amb.agreement'].search([
            ('payment_id', '=', self.id)
        ], limit=1)
        
        if existing_agreement:
            # Open existing contract
            return {
                'name': ('Contract'),
                'view_mode': 'form',
                'res_model': 'amb.agreement',
                'res_id': existing_agreement.id,
                'type': 'ir.actions.act_window',
            }
        
        # Auto-select template based on program_type
        template_id = False
        program_type = self.program_type
        
        # Try to find template matching program_type
        if program_type:
            template = self.env['amb.agreement.template'].search([
                ('program_type', '=', program_type.id),
                ('active', '=', True),
            ], limit=1)
            if template:
                template_id = template.id
        
        # Fallback: find any active template matching agreement_type
        if not template_id:
            # Map program types to agreement types
            type_mapping = {
                'study_visa': 'study_visa',
                'work_permit': 'work_permit',
                'immigration': 'immigration',
            }
            agreement_type = type_mapping.get(program_type.categ_id.name.lower() if program_type.categ_id else '', 'service')
            
            template = self.env['amb.agreement.template'].search([
                ('agreement_type', '=', agreement_type),
                ('active', '=', True),
            ], limit=1)
            if template:
                template_id = template.id
        
        # Create the agreement
        agreement_vals = {
            'partner_id': self.partner_id.id,
            'opportunity_id': self.opportunity_id.id if self.opportunity_id else False,
            'assessment_id': self.assessment_id.id if self.assessment_id else False,
            'payment_id': self.id,
            'program_type': program_type.id if program_type else False,
            'template_id': template_id,
            'total_fee': self.amount,
            'state': 'draft',
        }
        
        # Set agreement_type from template if found
        if template_id:
            template = self.env['amb.agreement.template'].browse(template_id)
            agreement_vals['agreement_type'] = template.agreement_type
        
        agreement = self.env['amb.agreement'].create(agreement_vals)
        
        # Map fields from customer and payment into contract content
        agreement.map_fields()
        
        return {
            'name': ('Contract'),
            'view_mode': 'form',
            'res_model': 'amb.agreement',
            'res_id': agreement.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_contract(self):
        """View contract linked to this payment"""
        self.ensure_one()
        
        agreement = self.env['amb.agreement'].search([
            ('payment_id', '=', self.id)
        ], limit=1)
        
        if not agreement:
            raise ValidationError('No contract found for this payment.')
        
        return {
            'name': ('Contract'),
            'view_mode': 'form',
            'res_model': 'amb.agreement',
            'res_id': agreement.id,
            'type': 'ir.actions.act_window',
        }

    def action_send_receipt(self):
        """Send receipt to customer"""
        self.ensure_one()
        if not self.receipt_number:
            self.action_generate_receipt()
        template = self.env.ref('amb_crm.email_template_payment_receipt')
        if template:
            template.send_mail(self.id, force_send=True)
        return {'type': 'ir.actions.act_window_close'}

    @api.constrains('amount', 'expected_amount')
    def _check_amount(self):
        """Validate payment amount"""
        for rec in self:
            if rec.amount < 0:
                raise ValidationError('Payment amount cannot be negative')

    # Removed payment_date validation constraint - allow future dates
    # @api.constrains('payment_date')
    # def _check_payment_date(self):
    #     """Validate payment date"""
    #     for rec in self:
    #         if rec.payment_date and rec.payment_date > fields.Date.today():
    #             raise ValidationError('Payment date cannot be in the future')
