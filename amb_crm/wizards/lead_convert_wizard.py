# -*- coding: utf-8 -*-
"""
Lead Convert Wizard for AMB CRM

Converts leads to opportunities with pre-filled data.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbLeadConvertWizard(models.TransientModel):
    """Lead Convert Wizard"""
    _name = 'amb.lead.convert.wizard'
    _description = 'Convert Lead to Opportunity'

    lead_id = fields.Many2one(
        'amb.lead',
        string='Lead',
        required=True,
    )

    # Pre-filled from lead
    partner_name = fields.Char(
        string='Customer Name',
        required=True,
    )

    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')

    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('other', 'Other'),
    ], string='Destination Country')

    program_interest = fields.Many2one(
        'product.product',
        string='Program Interest',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
    )

    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
    )

    team_id = fields.Many2one('crm.team', string='Team')

    # Options
    create_partner = fields.Boolean(
        string='Create Customer Record',
        default=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Existing Customer',
    )

    notes = fields.Text(string='Notes')

    @api.onchange('lead_id')
    def _onchange_lead(self):
        """Pre-fill from lead"""
        if self.lead_id:
            self.partner_name = self.lead_id.partner_name
            self.email = self.lead_id.email
            self.phone = self.lead_id.phone
            self.destination_country = self.lead_id.destination_country
            # Get program_interest from lead using mapped record values
            program = self.lead_id.program_interest
            if program and program.id:
                self.program_interest = program.id
            else:
                self.program_interest = False
            self.user_id = self.lead_id.user_id
            self.team_id = self.lead_id.team_id

    @api.onchange('create_partner', 'partner_name')
    def _onchange_partner_option(self):
        """Handle partner selection"""
        if self.create_partner:
            self.partner_id = False
        else:
            # Search for existing partner
            if self.partner_name:
                partners = self.env['res.partner'].search([
                    ('name', 'ilike', self.partner_name),
                ], limit=1)
                if partners:
                    self.partner_id = partners[0].id

    def action_convert(self):
        """Convert lead to opportunity"""
        self.ensure_one()
        
        # Create or get partner
        if self.create_partner:
            partner = self.env['res.partner'].create({
                'name': self.partner_name,
                'email': self.email,
                'phone': self.phone,
            })
        elif self.partner_id:
            partner = self.partner_id
        else:
            # Create minimal partner
            partner = self.env['res.partner'].create({
                'name': self.partner_name,
                'email': self.email,
                'phone': self.phone,
            })
        
        # Create opportunity
        opportunity_vals = {
            'partner_id': partner.id,
            'destination_country': self.destination_country,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'stage': 'new',
            'consultation_notes': self.notes,
            'work_experience_years': self.lead_id.total_work_experience if self.lead_id else 0,
        }
        
        # Safely set program_interest if it's a valid product
        if self.program_interest and self.program_interest._name == 'product.product' and self.program_interest.id:
            opportunity_vals['program_interest'] = self.program_interest.id
        
        if self.lead_id:
            opportunity_vals['lead_id'] = self.lead_id.id
        
        opportunity = self.env['amb.opportunity'].create(opportunity_vals)
        
        # Update lead
        if self.lead_id:
            self.lead_id.write({
                'state': 'converted',
                'opportunity_id': opportunity.id,
            })
        
        # Copy work history from lead to opportunity
        if self.lead_id and self.lead_id.work_history_ids:
            for wh in self.lead_id.work_history_ids:
                self.env['amb.work.history'].create({
                    'opportunity_id': opportunity.id,
                    'company_name': wh.company_name,
                    'position': wh.position,
                    'job_description': wh.job_description,
                    'years_employed': wh.years_employed,
                    'months_employed': wh.months_employed,
                    'start_date': wh.start_date,
                    'end_date': wh.end_date,
                    'is_current': wh.is_current,
                })
        
        return {
            'name': ('Opportunity Created'),
            'view_mode': 'form',
            'res_model': 'amb.opportunity',
            'res_id': opportunity.id,
            'type': 'ir.actions.act_window',
        }