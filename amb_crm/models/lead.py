# -*- coding: utf-8 -*-
"""
Lead Model for AMB CRM

Captures initial inquiries and converts them to opportunities.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbLead(models.Model):
    """Lead Model - Captures initial inquiries"""
    _name = 'amb.lead'
    _description = 'AMB Lead'
    _order = 'create_date desc, name asc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Reference and Name
    name = fields.Char(
        string='Lead Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )

    # Contact Information
    partner_name = fields.Char(
        string='Full Name',
        required=True,
        tracking=True,
    )

    email = fields.Char(
        string='Email',
        tracking=True,
    )

    phone = fields.Char(
        string='Phone',
        tracking=True,
    )

    mobile = fields.Char(
        string='Mobile',
    )

    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char(string='ZIP')

    # Lead Profiling
    nationality_id = fields.Many2one(
        'res.country',
        string='Nationality',
        tracking=True,
    )

    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('other', 'Other'),
    ], string='Destination Country', tracking=True)

    program_interest = fields.Many2one(
        'product.product',
        string='Program Interest',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
        tracking=True,
    )

    # Additional Info
    age = fields.Integer(string='Age', tracking=True)
    education_level = fields.Selection([
        ('high_school', 'High School'),
        ('diploma', 'Diploma'),
        ('bachelor', 'Bachelor Degree'),
        ('master', 'Master Degree'),
        ('phd', 'PhD'),
    ], string='Education Level')

    occupation = fields.Char(string='Current Occupation')
    
    # Work History - One2many for detailed work experience
    work_history_ids = fields.One2many('amb.work.history', 'lead_id', string='Work History')
    
    # Computed total work experience from work history
    total_work_experience = fields.Float(
        string='Total Work Experience (Years)',
        compute='_compute_total_work_experience',
        store=True,
    )

    @api.depends('work_history_ids.total_years')
    def _compute_total_work_experience(self):
        for rec in self:
            rec.total_work_experience = sum(rec.work_history_ids.mapped('total_years'))

    # Language Scores
    has_ielts = fields.Boolean(string='Has IELTS Score')
    ielts_score = fields.Float(string='IELTS Score', digits=(3, 1))
    has_celpip = fields.Boolean(string='Has CELPIP Score')
    celpip_score = fields.Float(string='CELPIP Score', digits=(3, 1))

    # Source Tracking
    source = fields.Selection([
        ('website', 'Website'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('whatsapp', 'WhatsApp'),
        ('referral', 'Referral'),
        ('seminar', 'Seminar/Webinar'),
        ('partner', 'Partner/Agent'),
        ('walk_in', 'Walk-in'),
        ('phone_call', 'Phone Call'),
        ('email', 'Email Campaign'),
        ('other', 'Other'),
    ], string='Lead Source', tracking=True, default='website')

    referral_source_id = fields.Many2one(
        'amb.partner.agent',
        string='Referral Agent/Partner',
    )

    # Marketing Campaign
    campaign_id = fields.Many2one('utm.campaign', string='Campaign')
    medium_id = fields.Many2one('utm.medium', string='Medium')

    # Lead Status
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='medium', tracking=True)

    state = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('not_interested', 'Not Interested'),
        ('converted', 'Converted to Opportunity'),
    ], string='Status', default='new', tracking=True, copy=False)

    # Assignment
    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        tracking=True,
        default=lambda self: self.env.user,
    )

    team_id = fields.Many2one('crm.team', string='Sales Team')

    # Qualification Notes
    notes = fields.Text(string='Notes')
    qualification_summary = fields.Text(string='Qualification Summary')

    # Appointment
    appointment_date = fields.Datetime(string='Appointment Date')
    appointment_location = fields.Char(string='Appointment Location')

    # Budget Estimate
    budget_amount = fields.Monetary(string='Budget Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id.id)

    # Timeline
    follow_up_date = fields.Date(string='Next Follow-up Date')
    last_follow_up_date = fields.Datetime(string='Last Follow-up', readonly=True)

    # Conversed Opportunity Link
    opportunity_id = fields.Many2one(
        'amb.opportunity',
        string='Converted Opportunity',
        readonly=True,
        copy=False,
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

    # Computed field for full address
    full_address = fields.Char(
        string='Full Address',
        compute='_compute_full_address',
        store=True,
    )

    @api.depends('street', 'street2', 'city', 'state_id', 'country_id', 'zip')
    def _compute_full_address(self):
        for rec in self:
            parts = []
            if rec.street:
                parts.append(rec.street)
            if rec.street2:
                parts.append(rec.street2)
            if rec.city:
                parts.append(rec.city)
            if rec.state_id:
                parts.append(rec.state_id.name)
            if rec.country_id:
                parts.append(rec.country_id.name)
            if rec.zip:
                parts.append(rec.zip)
            rec.full_address = ', '.join(parts) if parts else ''

    @api.model
    def create(self, vals_list):
        """Generate sequence for new leads"""
        # Handle both single dict and list of dicts
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amb.lead') or 'New'
        
        return super().create(vals_list)

    # === Action Methods ===

    def action_convert_to_opportunity(self):
        """Convert lead to opportunity using wizard"""
        self.ensure_one()
        ctx = self.env.context.copy()
        ctx.update({
            'default_lead_id': self.id,
            'default_partner_name': self.partner_name,
            'default_email': self.email,
            'default_phone': self.phone,
            'default_destination_country': self.destination_country,
            'default_user_id': self.user_id.id,
        })
        if self.program_interest and self.program_interest.id:
            ctx['default_program_interest'] = self.program_interest.id
        return {
            'name': ('Convert to Opportunity'),
            'view_mode': 'form',
            'res_model': 'amb.lead.convert.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx,
        }

    def action_view_opportunity(self):
        """Open the converted opportunity"""
        self.ensure_one()
        if self.opportunity_id:
            return {
                'name': ('Opportunity'),
                'view_mode': 'form',
                'res_model': 'amb.opportunity',
                'res_id': self.opportunity_id.id,
                'type': 'ir.actions.act_window',
            }

    def action_mark_contacted(self):
        """Mark lead as contacted"""
        for lead in self:
            lead.write({
                'state': 'contacted',
                'last_follow_up_date': fields.Datetime.now(),
            })

    def action_mark_qualified(self):
        """Mark lead as qualified"""
        for lead in self:
            lead.write({'state': 'qualified'})

    def action_mark_not_interested(self):
        """Mark lead as not interested"""
        for lead in self:
            lead.write({'state': 'not_interested'})

    def action_reopen(self):
        """Reopen a closed lead"""
        for lead in self:
            lead.write({'state': 'new'})

    def action_schedule_appointment(self):
        """Schedule appointment with lead"""
        self.ensure_one()
        return {
            'name': ('Schedule Appointment'),
            'view_mode': 'form',
            'res_model': 'calendar.event',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_name': 'Appointment with %s' % self.partner_name,
                'default_partner_ids': [(4, self.id)],
                'default_user_id': self.user_id.id,
            },
        }

    def action_send_email(self):
        """Send email to lead"""
        self.ensure_one()
        template = self.env.ref('amb_crm.email_template_lead_followup')
        if template:
            template.send_mail(self.id, force_send=True)

    def action_create_lead_report(self):
        """Generate lead report"""
        return self.env.ref('amb_crm.action_lead_report').report_action(self)


class AmbPartnerAgent(models.Model):
    """Partner/Agent Model for referral tracking"""
    _name = 'amb.partner.agent'
    _description = 'Partner/Agent'
    _inherit = ['mail.thread']

    name = fields.Char(string='Agent/Partner Name', required=True)
    partner_type = fields.Selection([
        ('agent', 'Immigration Agent'),
        ('educational', 'Educational Institution'),
        ('corporate', 'Corporate Partner'),
        ('individual', 'Individual Referral'),
    ], string='Type', default='individual')

    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    commission_percentage = fields.Float(string='Commission %', default=0.0)

    active = fields.Boolean(string='Active', default=True)

    lead_ids = fields.One2many('amb.lead', 'referral_source_id', string='Referral Leads')

    lead_count = fields.Integer(
        string='Lead Count',
        compute='_compute_lead_count',
    )

    converted_count = fields.Integer(
        string='Converted Count',
        compute='_compute_converted_count',
    )

    @api.depends('lead_ids')
    def _compute_lead_count(self):
        for rec in self:
            rec.lead_count = len(rec.lead_ids)

    @api.depends('lead_ids', 'lead_ids.opportunity_id')
    def _compute_converted_count(self):
        for rec in self:
            converted = rec.lead_ids.filtered(lambda l: l.opportunity_id)
            rec.converted_count = len(converted)