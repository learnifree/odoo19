# -*- coding: utf-8 -*-
"""
Opportunity Model for AMB CRM

Manages the sales pipeline from lead conversion to active client.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbOpportunity(models.Model):
    """Opportunity Model - Sales Pipeline"""
    _name = 'amb.opportunity'
    _description = 'AMB Opportunity'
    _order = 'priority desc, create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Reference
    name = fields.Char(
        string='Opportunity Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    # Lead Link
    lead_id = fields.Many2one(
        'amb.lead',
        string='Source Lead',
        tracking=True,
    )

    # Partner (Customer)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
    )

    partner_name = fields.Char(
        string='Customer Name',
        related='partner_id.name',
        store=True,
    )

    partner_email = fields.Char(
        string='Email',
        related='partner_id.email',
        store=True,
    )

    partner_phone = fields.Char(
        string='Phone',
        related='partner_id.phone',
        store=True,
    )

    # Contact details
    contact_name = fields.Char(string='Contact Person')
    contact_email = fields.Char(string='Contact Email')
    contact_phone = fields.Char(string='Contact Phone')

    # Destination & Program
    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('other', 'Other'),
    ], string='Destination Country', tracking=True, index=True)

    program_interest = fields.Many2one(
        'product.product',
        string='Program Interest',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
        tracking=True,
        index=True,
    )

    # Pipeline Stage
    stage = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('assessment', 'For Assessment'),
        ('negotiation', 'Negotiation'),
        ('payment', 'Payment Pending'),
        ('agreement', 'Agreement Signing'),
        ('converted', 'Converted to Client'),
        ('lost', 'Lost'),
    ], string='Stage', default='new', tracking=True, copy=False, index=True)

    # Stage Description
    stage_description = fields.Text(string='Stage Notes')

    # Priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='medium', tracking=True)

    # Assignment
    user_id = fields.Many2one(
        'res.users',
        string='Consultant/Sales Agent',
        tracking=True,
        default=lambda self: self.env.user,
    )

    team_id = fields.Many2one('crm.team', string='Team')

    # Revenue Estimate
    planned_revenue = fields.Monetary(
        string='Expected Revenue',
        currency_field='currency_id',
        tracking=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
    )

    # Consultation Notes
    consultation_notes = fields.Text(string='Consultation Notes')
    call_log = fields.Text(string='Call Log')
    meeting_summary = fields.Text(string='Meeting Summary')

    # Document attachments
    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
    )

    # Timeline
    next_follow_up = fields.Date(string='Next Follow-up')
    last_contact_date = fields.Datetime(string='Last Contact', readonly=True)

    # Related Records
    assessment_ids = fields.One2many('amb.assessment', 'opportunity_id', string='Assessments')
    
    # Work History
    work_history_ids = fields.One2many('amb.work.history', 'opportunity_id', string='Work History')
    
    # Computed total work experience from work history
    work_experience_years = fields.Float(
        string='Work Experience (Years)',
        compute='_compute_work_experience_years',
        store=True,
    )
    
    payment_ids = fields.One2many('amb.payment', 'opportunity_id', string='Payments')
    agreement_ids = fields.One2many('amb.agreement', 'opportunity_id', string='Agreements')

    # Client Case (after conversion)
    client_case_id = fields.Many2one(
        'amb.client.case',
        string='Client Case',
        readonly=True,
    )

    # Computed fields
    assessment_count = fields.Integer(compute='_compute_assessment_count', store=True)
    payment_count = fields.Integer(compute='_compute_payment_count', store=True)
    agreement_count = fields.Integer(compute='_compute_agreement_count', store=True)

    total_payment = fields.Monetary(
        string='Total Paid',
        currency_field='currency_id',
        compute='_compute_total_payment',
    )

    # Company link
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # Active flag
    active = fields.Boolean(string='Active', default=True)

    # Lost reasons
    lost_reason = fields.Text(string='Lost Reason')
    lost_date = fields.Date(string='Lost Date')

    @api.depends('work_history_ids', 'work_history_ids.total_years')
    def _compute_work_experience_years(self):
        for rec in self:
            rec.work_experience_years = sum(rec.work_history_ids.mapped('total_years') or [0.0])

    @api.depends('assessment_ids')
    def _compute_assessment_count(self):
        for rec in self:
            rec.assessment_count = len(rec.assessment_ids)

    @api.depends('payment_ids', 'payment_ids.amount')
    def _compute_total_payment(self):
        for rec in self:
            paid = rec.payment_ids.filtered(lambda p: p.state == 'paid')
            rec.total_payment = sum(paid.mapped('amount'))

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends('agreement_ids')
    def _compute_agreement_count(self):
        for rec in self:
            rec.agreement_count = len(rec.agreement_ids)

    def _compute_document_count(self):
        for rec in self:
            # Count attachments across related models
            count = 0
            for assessment in rec.assessment_ids:
                count += len(assessment.attachment_ids)
            rec.document_count = count

    @api.model
    @api.model
    def create(self, vals_list):
        """Generate sequence for new opportunities"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amb.opportunity') or 'New'
        
        return super().create(vals_list)

    # === Stage Actions ===

    def action_mark_contacted(self):
        """Mark opportunity as contacted"""
        for opp in self:
            opp.write({
                'stage': 'contacted',
                'last_contact_date': fields.Datetime.now(),
            })

    def action_mark_qualified(self):
        """Mark opportunity as qualified"""
        for opp in self:
            opp.write({'stage': 'qualified'})

    def action_send_for_assessment(self):
        """Move to assessment stage"""
        for opp in self:
            opp.write({'stage': 'assessment'})

    def action_start_negotiation(self):
        """Move to negotiation stage"""
        for opp in self:
            opp.write({'stage': 'negotiation'})

    def action_mark_payment_pending(self):
        """Move to payment pending stage"""
        for opp in self:
            opp.write({'stage': 'payment'})

    def action_sign_agreement(self):
        """Move to agreement signing stage"""
        for opp in self:
            opp.write({'stage': 'agreement'})

    def action_convert_to_client(self):
        """Convert opportunity to active client"""
        self.ensure_one()
        return {
            'name': ('Convert to Client'),
            'view_mode': 'form',
            'res_model': 'amb.opportunity.convert.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_opportunity_id': self.id,
            },
        }

    def action_mark_lost(self):
        """Mark opportunity as lost"""
        for opp in self:
            opp.write({
                'stage': 'lost',
                'active': False,
                'lost_date': fields.Date.today(),
            })

    def action_reopen(self):
        """Reopen a lost opportunity"""
        for opp in self:
            opp.write({
                'stage': 'new',
                'active': True,
                'lost_reason': False,
                'lost_date': False,
            })

    # === Quick Actions ===

    def action_create_assessment(self):
        """Create new assessment for this opportunity using wizard"""
        self.ensure_one()
        ctx = self.env.context.copy()
        ctx.update({
            'default_opportunity_id': self.id,
        })
        if self.program_interest and self.program_interest.id:
            ctx['default_program_type'] = self.program_interest.id
        return {
            'name': ('Create Assessment'),
            'view_mode': 'form',
            'res_model': 'amb.assessment.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx,
        }

    def action_view_assessments(self):
        """View all assessments for this opportunity"""
        self.ensure_one()
        return {
            'name': ('Assessments'),
            'view_mode': 'tree,form',
            'res_model': 'amb.assessment',
            'type': 'ir.actions.act_window',
            'domain': [('opportunity_id', '=', self.id)],
        }

    def action_view_payments(self):
        """View all payments for this opportunity"""
        self.ensure_one()
        return {
            'name': ('Payments'),
            'view_mode': 'tree,form',
            'res_model': 'amb.payment',
            'type': 'ir.actions.act_window',
            'domain': [('opportunity_id', '=', self.id)],
        }

    def action_view_agreements(self):
        """View all agreements for this opportunity"""
        self.ensure_one()
        return {
            'name': ('Agreements'),
            'view_mode': 'tree,form',
            'res_model': 'amb.agreement',
            'type': 'ir.actions.act_window',
            'domain': [('opportunity_id', '=', self.id)],
        }

    def action_schedule_follow_up(self):
        """Schedule follow-up activity"""
        self.ensure_one()
        return {
            'name': ('Schedule Follow-up'),
            'view_mode': 'form',
            'res_model': 'calendar.event',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_name': 'Follow-up: %s' % self.name,
                'default_partner_id': self.partner_id.id,
                'default_user_id': self.user_id.id,
            },
        }

    def write(self, vals):
        """Override write to track last contact date"""
        if 'stage' in vals and vals['stage'] != self.stage:
            vals['last_contact_date'] = fields.Datetime.now()
        return super().write(vals)

    @api.constrains('stage', 'assessment_ids')
    def _check_stage_progression(self):
        """Validate stage progression"""
        for opp in self:
            # Can only create agreement if assessment exists
            if opp.agreement_ids and not opp.assessment_ids:
                pass  # Allow for direct contracts
