# -*- coding: utf-8 -*-
"""
Service Package Model for AMB CRM

Defines service packages that can be sold to customers.
"""

from odoo import models, fields, api


class AmbServicePackage(models.Model):
    """Service Package Model"""
    _name = 'amb.service.package'
    _description = 'AMB Service Package'
    _order = 'sequence asc, name asc'

    name = fields.Char(
        string='Package Name',
        required=True,
    )

    code = fields.Char(
        string='Code',
        required=True,
    )

    description = fields.Text(string='Description')

    # Package Type
    package_type = fields.Selection([
        ('pr', 'Permanent Residency'),
        ('study', 'Study Visa'),
        ('work', 'Work Permit'),
        ('visitor', 'Visitor Visa'),
        ('business', 'Business Visa'),
        ('assessment', 'Assessment Only'),
        ('document', 'Document Review'),
        ('consultation', 'Consultation'),
        ('other', 'Other'),
    ], string='Package Type', required=True)

    # Destination Country
    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('multiple', 'Multiple'),
        ('other', 'Other'),
    ], string='Destination Country')

    # Fee Structure
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    base_fee = fields.Monetary(
        string='Base Fee',
        currency_field='currency_id',
        required=True,
    )

    assessment_fee = fields.Monetary(
        string='Assessment Fee',
        currency_field='currency_id',
        default=0,
    )

    processing_fee = fields.Monetary(
        string='Processing Fee',
        currency_field='currency_id',
        default=0,
    )

    government_fee = fields.Monetary(
        string='Government Fees (Est.)',
        currency_field='currency_id',
        default=0,
    )

    total_fee = fields.Monetary(
        string='Total Fee',
        currency_field='currency_id',
        compute='_compute_total_fee',
        store=True,
    )

    # Services Included
    service_items = fields.Text(string='Services Included')
    deliverables = fields.Text(string='Deliverables')
    
    # Timeline
    estimated_duration = fields.Char(string='Estimated Duration')
    processing_time = fields.Char(string='Processing Time')

    # Payment Options
    allow_installment = fields.Boolean(string='Allow Installments', default=True)
    min_deposit_percentage = fields.Float(
        string='Minimum Deposit %',
        default=30.0,
    )

    number_of_installments = fields.Integer(
        string='Number of Installments',
        default=3,
    )

    # Status
    active = fields.Boolean(string='Active', default=True)

    # Sequence for ordering
    sequence = fields.Integer(string='Sequence', default=10)

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # Product Link
    product_id = fields.Many2one(
        'product.product',
        string='Linked Product',
        domain="[('categ_id.name', 'ilike', 'immigration')]",
        help='Links to Odoo product for invoicing. Only products with immigration category are shown.',
    )

    product_name = fields.Char(
        string='Product Name',
        related='product_id.name',
        readonly=False,
    )

    product_sale_price = fields.Float(
        string='Sale Price',
        related='product_id.list_price',
        readonly=False,
    )

    # Usage tracking
    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count',
        store=True,
    )

    @api.depends('base_fee', 'assessment_fee', 'processing_fee', 'government_fee')
    def _compute_total_fee(self):
        for rec in self:
            rec.total_fee = (
                (rec.base_fee or 0) + 
                (rec.assessment_fee or 0) + 
                (rec.processing_fee or 0) + 
                (rec.government_fee or 0)
            )

    @api.depends()
    def _compute_usage_count(self):
        for rec in self:
            rec.usage_count = self.env['amb.proposal'].search_count([
                ('service_package_id', '=', rec.id)
            ])

    @api.constrains('code')
    def _check_code_unique(self):
        """Ensure package code is unique per company"""
        for rec in self:
            existing = self.search([
                ('code', '=', rec.code),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(
                    'Package code must be unique per company: %s' % rec.code
                )

    def action_view_usage(self):
        """View proposals using this package"""
        self.ensure_one()
        return {
            'name': ('Proposals'),
            'view_mode': 'tree,form',
            'res_model': 'amb.proposal',
            'type': 'ir.actions.act_window',
            'domain': [('service_package_id', '=', self.id)],
        }


class AmbServiceItem(models.Model):
    """Individual Service Item within a package"""
    _name = 'amb.service.item'
    _description = 'AMB Service Item'

    name = fields.Char(
        string='Service Item',
        required=True,
    )

    description = fields.Text(string='Description')

    package_id = fields.Many2one(
        'amb.service.package',
        string='Package',
    )

    sequence = fields.Integer(string='Sequence', default=10)

    included = fields.Boolean(string='Included', default=True)
    additional_fee = fields.Monetary(
        string='Additional Fee',
        currency_field='currency_id',
        default=0,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
    )

    active = fields.Boolean(string='Active', default=True)