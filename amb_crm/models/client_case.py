# -*- coding: utf-8 -*-
"""
Client Case Model for AMB CRM

Manages active client cases after opportunity conversion.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbClientCase(models.Model):
    """Client Case Model - Active Case Management"""
    _name = 'amb.client.case'
    _description = 'AMB Client Case'
    _order = 'priority desc, create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Reference
    name = fields.Char(
        string='Case Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    # Opportunity Link (source)
    opportunity_id = fields.Many2one(
        'amb.opportunity',
        string='Source Opportunity',
        readonly=True,
        tracking=True,
    )

    # Partner (Customer)
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
    )

    partner_name = fields.Char(
        string='Client Name',
        related='partner_id.name',
        store=True,
    )

    # Program Details
    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('other', 'Other'),
    ], string='Destination Country', tracking=True)

    program_type = fields.Selection([
        ('express_entry', 'Express Entry'),
        ('provincial_nomination', 'Provincial Nomination'),
        ('skilled_worker', 'Skilled Worker'),
        ('study_visa', 'Study Visa'),
        ('work_permit', 'Work Permit'),
        ('visitor_visa', 'Visitor Visa'),
        ('business_visa', 'Business Visa'),
        ('immigration', 'Immigration'),
        ('other', 'Other'),
    ], string='Program Type', tracking=True)

    # Case Status
    state = fields.Selection([
        ('active', 'Active'),
        ('pending_docs', 'Pending Documents'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold'),
        ('closed', 'Closed'),
    ], string='Case Status', default='active', tracking=True, copy=False, index=True)

    # Case Priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='medium', tracking=True)

    # Case Officer Assignment
    case_officer_id = fields.Many2one(
        'res.users',
        string='Case Officer',
        tracking=True,
    )

    team_id = fields.Many2one('crm.team', string='Team')

    # Timeline
    case_start_date = fields.Date(
        string='Case Start Date',
        default=fields.Date.context_today,
    )

    target_date = fields.Date(string='Target Completion Date')
    submitted_date = fields.Date(string='Submitted Date', readonly=True)
    decision_date = fields.Date(string='Decision Date', readonly=True)

    # Case Details
    case_description = fields.Text(string='Case Description')
    case_notes = fields.Text(string='Case Notes')

    # Document Management
    document_ids = fields.Many2many(
        'ir.attachment',
        'amb_client_case_document_rel',
        'case_id',
        'attachment_id',
        string='Case Documents',
    )

    document_count = fields.Integer(
        string='Documents',
        compute='_compute_document_count',
    )

    # Related Records
    assessment_ids = fields.One2many(
        'amb.assessment',
        'case_id',
        string='Assessments',
    )

    payment_ids = fields.One2many(
        'amb.payment',
        'case_id',
        string='Payments',
    )

    agreement_ids = fields.One2many(
        'amb.agreement',
        'case_id',
        string='Agreements',
    )

    # Computed
    total_paid = fields.Monetary(
        string='Total Paid',
        currency_field='currency_id',
        compute='_compute_total_paid',
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id.id,
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(string='Active', default=True)

    # Result
    result = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('pending', 'Pending'),
    ], string='Result', readonly=True)

    result_notes = fields.Text(string='Result Notes')

    @api.model
    def create(self, vals_list):
        """Generate sequence for new cases"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amb.client.case') or 'New'
        
        return super().create(vals_list)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    @api.depends('payment_ids', 'payment_ids.state', 'payment_ids.amount')
    def _compute_total_paid(self):
        for rec in self:
            paid = rec.payment_ids.filtered(lambda p: p.state == 'paid')
            rec.total_paid = sum(paid.mapped('amount'))

    # === Action Methods ===

    def action_view_opportunity(self):
        """View source opportunity"""
        self.ensure_one()
        if self.opportunity_id:
            return {
                'name': ('Opportunity'),
                'view_mode': 'form',
                'res_model': 'amb.opportunity',
                'res_id': self.opportunity_id.id,
                'type': 'ir.actions.act_window',
            }

    def action_view_assessments(self):
        """View all assessments for this case"""
        self.ensure_one()
        return {
            'name': ('Assessments'),
            'view_mode': 'tree,form',
            'res_model': 'amb.assessment',
            'type': 'ir.actions.act_window',
            'domain': [('case_id', '=', self.id)],
        }

    def action_view_payments(self):
        """View all payments for this case"""
        self.ensure_one()
        return {
            'name': ('Payments'),
            'view_mode': 'tree,form',
            'res_model': 'amb.payment',
            'type': 'ir.actions.act_window',
            'domain': [('case_id', '=', self.id)],
        }

    def action_view_agreements(self):
        """View all agreements for this case"""
        self.ensure_one()
        return {
            'name': ('Agreements'),
            'view_mode': 'tree,form',
            'res_model': 'amb.agreement',
            'type': 'ir.actions.act_window',
            'domain': [('case_id', '=', self.id)],
        }

    def action_mark_submitted(self):
        """Mark case as submitted"""
        for case in self:
            case.write({
                'state': 'submitted',
                'submitted_date': fields.Date.today(),
            })

    def action_mark_under_review(self):
        """Mark case as under review"""
        for case in self:
            case.write({'state': 'under_review'})

    def action_mark_approved(self):
        """Mark case as approved"""
        for case in self:
            case.write({
                'state': 'approved',
                'result': 'approved',
                'decision_date': fields.Date.today(),
            })

    def action_mark_rejected(self):
        """Mark case as rejected"""
        for case in self:
            case.write({
                'state': 'rejected',
                'result': 'rejected',
                'decision_date': fields.Date.today(),
            })

    def action_mark_pending_docs(self):
        """Mark case as pending documents"""
        for case in self:
            case.write({'state': 'pending_docs'})

    def action_close_case(self):
        """Close the case"""
        for case in self:
            case.write({'state': 'closed'})

    def action_create_activity(self):
        """Schedule follow-up activity"""
        self.ensure_one()
        return {
            'name': ('Schedule Activity'),
            'view_mode': 'form',
            'res_model': 'mail.activity',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_res_model': 'amb.client.case',
                'default_res_id': self.id,
                'default_user_id': self.case_officer_id.id or self.env.user.id,
            },
        }

    def action_print_case_summary(self):
        """Print case summary report"""
        self.ensure_one()
        return self.env.ref('amb_crm.action_client_case_report').report_action(self)