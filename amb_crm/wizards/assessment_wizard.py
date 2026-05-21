# -*- coding: utf-8 -*-
"""
Assessment Wizard for AMB CRM

Helps create assessments with guided data entry.
"""

from odoo import models, fields, api


class AmbAssessmentWizard(models.TransientModel):
    """Assessment Wizard"""
    _name = 'amb.assessment.wizard'
    _description = 'Create Assessment'

    opportunity_id = fields.Many2one(
        'amb.opportunity',
        string='Opportunity',
        required=True,
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        readonly=True,
    )

    customer_name = fields.Char(
        string='Customer Name',
        readonly=True,
    )

    # Program Info
    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('other', 'Other'),
    ], string='Destination Country', default='canada')

    # Program type - relates to Odoo product (service type, immigration category)
    program_type = fields.Many2one(
        'product.product',
        string='Program Type',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
        required=True,
    )

    # Basic Info from partner
    age = fields.Integer(string='Age')
    education_level = fields.Selection([
        ('high_school', 'High School'),
        ('diploma', 'Diploma'),
        ('bachelors', "Bachelor's Degree"),
        ('masters', "Master's Degree"),
        ('phd', 'PhD'),
        ('other', 'Other'),
    ], string='Education Level')

    work_experience_years = fields.Integer(string='Work Experience (Years)')

    # Language
    language_test_type = fields.Selection([
        ('ielts', 'IELTS'),
        ('celpip', 'CELPIP'),
        ('pte', 'PTE Academic'),
        ('toefl', 'TOEFL'),
        ('other', 'Other'),
    ], string='Language Test')

    listening_score = fields.Float(string='Listening')
    reading_score = fields.Float(string='Reading')
    writing_score = fields.Float(string='Writing')
    speaking_score = fields.Float(string='Speaking')

    # CRS Score Preview
    crs_score = fields.Integer(
        string='CRS Score Preview',
        compute='_compute_crs_preview',
        store=False,
    )

    @api.onchange('opportunity_id')
    def _onchange_opportunity(self):
        """Pre-fill from opportunity"""
        if self.opportunity_id:
            self.partner_id = self.opportunity_id.partner_id
            self.customer_name = self.opportunity_id.partner_id.name or ''
            self.destination_country = self.opportunity_id.destination_country
            
            # Map program_interest from opportunity to program_type
            # First check if we have a context value (passed from opportunity action)
            ctx_program = self.env.context.get('default_program_type')
            if ctx_program:
                self.program_type = ctx_program
            else:
                # Fallback: get from opportunity's program_interest
                program = self.opportunity_id.program_interest
                if program:
                    if hasattr(program, 'id') and program.id:
                        # It's a valid product record - set the ID directly
                        self.program_type = program.id
                    elif isinstance(program, str):
                        # Old string value - try to find matching product by name
                        products = self.env['product.product'].search([
                            ('name', 'ilike', program),
                            ('type', '=', 'service'),
                        ], limit=1)
                        if products:
                            self.program_type = products[0].id
            
            # Fetch from source lead if available
            lead = self.opportunity_id.lead_id
            if lead:
                self.age = lead.age
                
                # Map education level from lead to wizard
                edu_map = {
                    'high_school': 'high_school',
                    'diploma': 'diploma',
                    'bachelor': 'bachelors',  # singular to plural
                    'bachelors': 'bachelors',
                    'master': 'masters',  # singular to plural
                    'masters': 'masters',
                    'phd': 'phd',
                }
                self.education_level = edu_map.get(lead.education_level, False)
                self.work_experience_years = self.opportunity_id.work_experience_years or lead.total_work_experience or 0

    @api.depends('age', 'education_level', 'work_experience_years', 
                 'language_test_type', 'listening_score', 'reading_score',
                 'writing_score', 'speaking_score')
    def _compute_crs_preview(self):
        """Compute CRS score preview"""
        for rec in self:
            # Age points
            age = rec.age or 0
            if 18 <= age <= 35:
                age_pts = 100
            elif 36 <= age <= 40:
                age_pts = 90
            elif 41 <= age <= 45:
                age_pts = 80
            elif 46 <= age <= 50:
                age_pts = 70
            else:
                age_pts = 0
            
            # Education points
            edu_map = {
                'high_school': 30, 'diploma': 70, 'bachelors': 120, 
                'masters': 135, 'phd': 150
            }
            edu_pts = edu_map.get(rec.education_level, 0)
            
            # Work experience points
            years = rec.work_experience_years or 0
            if years >= 6:
                work_pts = 80
            elif years == 5:
                work_pts = 75
            elif years == 4:
                work_pts = 70
            elif years == 3:
                work_pts = 65
            elif years == 2:
                work_pts = 55
            elif years == 1:
                work_pts = 40
            else:
                work_pts = 0
            
            # Language points (simplified)
            lang_pts = 0
            if rec.language_test_type and all([rec.listening_score, rec.reading_score, 
                                               rec.writing_score, rec.speaking_score]):
                avg = (rec.listening_score + rec.reading_score + 
                       rec.writing_score + rec.speaking_score) / 4
                if avg >= 8.5:
                    lang_pts = 124
                elif avg >= 8.0:
                    lang_pts = 116
                elif avg >= 7.5:
                    lang_pts = 108
                elif avg >= 7.0:
                    lang_pts = 92
                elif avg >= 6.5:
                    lang_pts = 80
                elif avg >= 6.0:
                    lang_pts = 68
                else:
                    lang_pts = 38
            
            rec.crs_score = age_pts + edu_pts + work_pts + lang_pts

    def action_create_assessment(self):
        """Create assessment from wizard and close"""
        self.ensure_one()
        
        assessment_vals = {
            'opportunity_id': self.opportunity_id.id,
            'destination_country': self.destination_country,
            'program_type': self.program_type.id if self.program_type else False,
            'age': self.age,
            'education_level': self.education_level,
            'work_experience_years': self.work_experience_years,
            'language_test_type': self.language_test_type,
            'listening_score': self.listening_score,
            'reading_score': self.reading_score,
            'writing_score': self.writing_score,
            'speaking_score': self.speaking_score,
        }
        
        assessment = self.env['amb.assessment'].create(assessment_vals)
        
        # Open the newly created assessment form
        return {
            'name': ('Assessment'),
            'view_mode': 'form',
            'res_model': 'amb.assessment',
            'res_id': assessment.id,
            'type': 'ir.actions.act_window',
        }
