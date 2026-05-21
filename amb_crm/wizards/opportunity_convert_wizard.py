# -*- coding: utf-8 -*-
"""
Opportunity Convert Wizard for AMB CRM

Converts opportunities to active client cases.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbOpportunityConvertWizard(models.TransientModel):
    """Opportunity Convert Wizard"""
    _name = 'amb.opportunity.convert.wizard'
    _description = 'Convert Opportunity to Client Case'

    opportunity_id = fields.Many2one(
        'amb.opportunity',
        string='Opportunity',
        required=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='opportunity_id.partner_id',
        readonly=True,
    )

    # Case Details
    destination_country = fields.Selection(
        related='opportunity_id.destination_country',
        readonly=True,
    )

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
    ], string='Program Type')

    case_officer_id = fields.Many2one(
        'res.users',
        string='Case Officer',
        default=lambda self: self.env.user,
    )

    team_id = fields.Many2one('crm.team', string='Team')

    case_description = fields.Text(string='Case Description')
    target_date = fields.Date(string='Target Completion Date')

    # Link existing records to case
    link_assessments = fields.Boolean(
        string='Link Existing Assessments',
        default=True,
    )

    link_payments = fields.Boolean(
        string='Link Existing Payments',
        default=True,
    )

    link_agreements = fields.Boolean(
        string='Link Existing Agreements',
        default=True,
    )

    @api.onchange('opportunity_id')
    def _onchange_opportunity(self):
        """Pre-fill from opportunity"""
        if self.opportunity_id:
            # Map program_interest to program_type
            program_map = {
                'pr': 'express_entry',
                'study_visa': 'study_visa',
                'work_permit': 'work_permit',
                'visitor_visa': 'visitor_visa',
                'business_visa': 'business_visa',
            }
            self.program_type = program_map.get(
                self.opportunity_id.program_interest, 'immigration'
            )
            self.team_id = self.opportunity_id.team_id

    def action_convert_to_client(self):
        """Convert opportunity to client case"""
        self.ensure_one()
        
        # Create client case
        case_vals = {
            'opportunity_id': self.opportunity_id.id,
            'partner_id': self.opportunity_id.partner_id.id,
            'destination_country': self.opportunity_id.destination_country,
            'program_type': self.program_type,
            'case_officer_id': self.case_officer_id.id,
            'team_id': self.team_id.id,
            'case_description': self.case_description,
            'target_date': self.target_date,
            'state': 'active',
        }
        
        client_case = self.env['amb.client.case'].create(case_vals)
        
        # Link existing records to case
        if self.link_assessments:
            for assessment in self.opportunity_id.assessment_ids:
                assessment.write({'case_id': client_case.id})
        
        if self.link_payments:
            for payment in self.opportunity_id.payment_ids:
                payment.write({'case_id': client_case.id})
        
        if self.link_agreements:
            for agreement in self.opportunity_id.agreement_ids:
                agreement.write({'case_id': client_case.id})
        
        # Update opportunity
        self.opportunity_id.write({
            'stage': 'converted',
            'client_case_id': client_case.id,
        })
        
        return {
            'name': ('Client Case: %s' % client_case.name),
            'view_mode': 'form',
            'res_model': 'amb.client.case',
            'res_id': client_case.id,
            'type': 'ir.actions.act_window',
        }