# -*- coding: utf-8 -*-
"""
Invoice Creation Wizard for AMB CRM

Allows users to create invoices from payments with customizable pricing.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbCreateInvoiceWizard(models.TransientModel):
    """Wizard to create invoice with custom pricing"""
    _name = 'amb.create.invoice.wizard'
    _description = 'Create Invoice Wizard'

    payment_id = fields.Many2one(
        'amb.payment',
        string='Payment',
        required=True,
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        required=True,
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
    )

    description = fields.Char(string='Description')

    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
    )

    unit_price = fields.Monetary(
        string='Unit Price',
        required=True,
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_amount',
        currency_field='currency_id',
    )

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
    )

    invoice_date = fields.Date(
        string='Invoice Date',
        default=fields.Date.context_today,
    )

    due_date = fields.Date(string='Due Date')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_price

    @api.onchange('product_id')
    def _onchange_product(self):
        """Auto-fill price from product"""
        if self.product_id:
            self.unit_price = self.product_id.list_price or 0.0
            self.description = self.product_id.name

    @api.onchange('payment_id')
    def _onchange_payment(self):
        """Pre-fill from payment"""
        if self.payment_id:
            self.currency_id = self.payment_id.currency_id.id
            self.company_id = self.payment_id.company_id.id
            # Pre-fill product from payment
            if self.payment_id.program_type:
                self.product_id = self.payment_id.program_type.id

    def action_create_invoice(self):
        """Create invoice with configured values"""
        self.ensure_one()

        # Validate
        if not self.product_id:
            raise ValidationError('Please select a Product/Service.')

        # Get journal if not set
        journal_id = self.journal_id
        if not journal_id:
            journal_id = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

        if not journal_id:
            raise ValidationError('Please configure a Sales Journal in Accounting.')

        # Get revenue account from product
        revenue_account_id = self.product_id.property_account_income_id.id
        if not revenue_account_id:
            revenue_account_id = journal_id.default_account_id.id

        # Build description
        description = self.description or self.product_id.name

        # Create invoice line
        invoice_line_vals = [(0, 0, {
            'product_id': self.product_id.id,
            'name': description,
            'quantity': self.quantity,
            'price_unit': self.unit_price,
            'account_id': revenue_account_id,
        })]

        # Build origin reference
        origin_ref = 'Payment: %s' % self.payment_id.name
        if self.payment_id.assessment_id:
            origin_ref += ' | Assessment: %s' % self.payment_id.assessment_id.name

        # Create invoice
        invoice_vals = {
            'partner_id': self.payment_id.partner_id.id,
            'move_type': 'out_invoice',
            'journal_id': journal_id.id,
            'invoice_date': self.invoice_date or fields.Date.today(),
            'invoice_line_ids': invoice_line_vals,
            'invoice_origin': origin_ref,
            'ref': origin_ref,
        }

        if self.due_date:
            invoice_vals['invoice_date_due'] = self.due_date

        invoice = self.env['account.move'].create(invoice_vals)

        # Link invoice to payment
        self.payment_id.write({'invoice_id': invoice.id})

        # Return action to open the invoice
        return {
            'name': 'Invoice Created',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }