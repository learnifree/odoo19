# -*- coding: utf-8 -*-
"""
Work History Model for AMB CRM

Tracks work experience for leads, opportunities and assessments.
"""

from odoo import models, fields, api
from datetime import date


class AmbWorkHistory(models.Model):
    """Work History Model"""
    _name = 'amb.work.history'
    _description = 'Work History'
    _order = 'sequence, id'

    company_name = fields.Char(
        string='Company Name',
        required=True,
    )

    position = fields.Char(
        string='Position/Title',
        required=True,
    )

    job_description = fields.Text(string='Job Description')

    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    is_current = fields.Boolean(string='Current Position', default=False)

    sequence = fields.Integer(string='Sequence', default=10)

    # Related records
    lead_id = fields.Many2one('amb.lead', string='Lead', ondelete='cascade')
    opportunity_id = fields.Many2one('amb.opportunity', string='Opportunity', ondelete='cascade')
    assessment_id = fields.Many2one('amb.assessment', string='Assessment', ondelete='cascade')

    # Computed years and months based on dates
    years_employed = fields.Integer(
        string='Years',
        compute='_compute_employment_duration',
        store=True,
        help='Number of years worked at this company',
    )

    months_employed = fields.Integer(
        string='Months',
        compute='_compute_employment_duration',
        store=True,
        help='Additional months worked',
    )

    # Compute total years
    total_years = fields.Float(
        string='Total Years',
        compute='_compute_employment_duration',
        store=True,
    )

    @api.depends('start_date', 'end_date', 'is_current')
    def _compute_employment_duration(self):
        """Calculate years, months and total from start and end dates"""
        for rec in self:
            if not rec.start_date:
                rec.years_employed = 0
                rec.months_employed = 0
                rec.total_years = 0.0
                continue
            
            # Use today if current position
            end = rec.end_date or date.today()
            start = rec.start_date
            
            # Calculate months difference
            months = (end.year - start.year) * 12 + (end.month - start.month)
            
            # Adjust for day of month
            if end.day < start.day:
                months -= 1
            
            # Calculate years and remaining months
            rec.years_employed = months // 12
            rec.months_employed = months % 12
            rec.total_years = months / 12.0

    @api.onchange('is_current')
    def _onchange_is_current(self):
        """Clear end date if current position"""
        if self.is_current:
            self.end_date = False