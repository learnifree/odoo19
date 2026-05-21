# -*- coding: utf-8 -*-
"""
Assessment Model for AMB CRM

Handles eligibility evaluation and CRS scoring for immigration programs.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AmbAssessment(models.Model):
    """Assessment Model - Eligibility Evaluation"""
    _name = 'amb.assessment'
    _description = 'AMB Assessment'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Reference
    name = fields.Char(
        string='Assessment Reference',
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

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='opportunity_id.partner_id',
        store=True,
    )

    customer_name = fields.Char(
        string='Customer Name',
        related='partner_id.name',
        store=True,
    )

    # Program Info
    destination_country = fields.Selection([
        ('canada', 'Canada'),
        ('australia', 'Australia'),
        ('usa', 'USA'),
        ('uk', 'United Kingdom'),
        ('new_zealand', 'New Zealand'),
        ('other', 'Other'),
    ], string='Destination Country', required=True)

    program_type = fields.Many2one(
        'product.product',
        string='Program Type',
        domain="[('type', '=', 'service'), ('categ_id.name', 'ilike', 'immigration')]",
        required=True,
    )

    # Personal Information
    age = fields.Integer(string='Age', tracking=True)
    education_level = fields.Selection([
        ('high_school', 'High School'),
        ('diploma', 'Diploma'),
        ('bachelors', "Bachelor's Degree"),
        ('masters', "Master's Degree"),
        ('phd', 'PhD'),
        ('other', 'Other'),
    ], string='Education Level', tracking=True)

    education_country_id = fields.Many2one('res.country', string='Education Country')
    education_field = fields.Char(string='Field of Study')

    # Work Experience
    work_experience_years = fields.Integer(string='Total Work Experience (Years)', tracking=True)
    work_experience_abroad = fields.Integer(string='Work Experience Abroad (Years)')
    
    # Work History - One2many for detailed work experience
    work_history_ids = fields.One2many('amb.work.history', 'assessment_id', string='Work History')

    # Language Scores
    language_test_type = fields.Selection([
        ('ielts', 'IELTS'),
        ('celpip', 'CELPIP'),
        ('pte', 'PTE Academic'),
        ('toefl', 'TOEFL'),
        ('other', 'Other'),
    ], string='Language Test Type', tracking=True)

    listening_score = fields.Float(string='Listening', digits=(3, 1))
    reading_score = fields.Float(string='Reading', digits=(3, 1))
    writing_score = fields.Float(string='Writing', digits=(3, 1))
    speaking_score = fields.Float(string='Speaking', digits=(3, 1))

    # Combined language score (computed)
    language_score = fields.Float(
        string='Language Score',
        compute='_compute_language_score',
        store=True,
    )

    has_french = fields.Boolean(string='Has French Language')
    french_score = fields.Float(string='French Score (TEF/TCF)', digits=(3, 1))

    # CRS Score (Canada Express Entry)
    crs_score = fields.Integer(
        string='CRS Score',
        compute='_compute_crs_score',
        store=True,
        tracking=True,
    )

    # Age Points
    age_points = fields.Integer(
        string='Age Points',
        compute='_compute_age_points',
        store=True,
    )

    # Education Points
    education_points = fields.Integer(
        string='Education Points',
        compute='_compute_education_points',
        store=True,
    )

    # Work Experience Points
    work_points = fields.Integer(
        string='Work Experience Points',
        compute='_compute_work_points',
        store=True,
    )

    # Language Points
    language_points = fields.Integer(
        string='Language Points',
        compute='_compute_language_points',
        store=True,
    )

    # Additional Points
    job_offer_points = fields.Integer(string='Job Offer Points', default=0)
    provincial_nomination_points = fields.Integer(string='Provincial Nomination Points', default=0)
    education_in_canada_points = fields.Integer(string='Canadian Education Points', default=0)
    foreign_work_experience_points = fields.Integer(string='Foreign Work Experience Points', default=0)
    sibling_in_canada_points = fields.Integer(string='Sibling Points', default=0)

    # Eligibility Result
    eligibility_status = fields.Selection([
        ('not_eligible', 'Not Eligible'),
        ('partially_eligible', 'Partially Eligible'),
        ('eligible', 'Eligible'),
        ('highly_eligible', 'Highly Eligible'),
    ], string='Eligibility Status', default='not_eligible', tracking=True, index=True)

    eligibility_score = fields.Integer(
        string='Eligibility Score',
        compute='_compute_eligibility_score',
        store=True,
    )

    # Assessment Details
    assessment_date = fields.Date(
        string='Assessment Date',
        default=fields.Date.context_today,
    )

    assessor_id = fields.Many2one(
        'res.users',
        string='Assessor',
        default=lambda self: self.env.user,
    )

    assessment_notes = fields.Html(string='Assessment Notes')
    strengths_weaknesses = fields.Html(string='Strengths & Weaknesses')

    # Recommendation
    recommended_program = fields.Char(string='Recommended Program')
    recommendation = fields.Text(string='Recommendation')

    # Supporting Documents
    document_ids = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents',
    )

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'amb_assessment_attachment_rel',
        'assessment_id',
        'attachment_id',
        string='Attachments',
    )

    # Next Steps
    next_steps = fields.Text(string='Next Steps')
    deadline_date = fields.Date(string='Deadline')

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', tracking=True, copy=False)

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(string='Active', default=True)

    @api.depends('listening_score', 'reading_score', 'writing_score', 'speaking_score', 'language_test_type')
    def _compute_language_score(self):
        for rec in self:
            if rec.language_test_type == 'celpip':
                # CELPIP is on 12 scale
                rec.language_score = (rec.listening_score + rec.reading_score + 
                                     rec.writing_score + rec.speaking_score) / 4
            else:
                # IELTS is on 9 scale
                rec.language_score = (rec.listening_score + rec.reading_score + 
                                     rec.writing_score + rec.speaking_score) / 4

    @api.depends('age')
    def _compute_age_points(self):
        for rec in self:
            age = rec.age or 0
            if 18 <= age <= 35:
                rec.age_points = 100
            elif 36 <= age <= 40:
                rec.age_points = 90
            elif 41 <= age <= 45:
                rec.age_points = 80
            elif 46 <= age <= 50:
                rec.age_points = 70
            else:
                rec.age_points = 0

    @api.depends('education_level')
    def _compute_education_points(self):
        for rec in self:
            edu = rec.education_level
            points_map = {
                'high_school': 30,
                'diploma': 70,
                'bachelors': 120,
                'masters': 135,
                'phd': 150,
            }
            rec.education_points = points_map.get(edu, 0)

    @api.depends('work_experience_years')
    def _compute_work_points(self):
        for rec in self:
            years = rec.work_experience_years or 0
            if years >= 6:
                rec.work_points = 80
            elif years == 5:
                rec.work_points = 75
            elif years == 4:
                rec.work_points = 70
            elif years == 3:
                rec.work_points = 65
            elif years == 2:
                rec.work_points = 55
            elif years == 1:
                rec.work_points = 40
            else:
                rec.work_points = 0

    @api.depends('language_score')
    def _compute_language_points(self):
        for rec in self:
            score = rec.language_score or 0
            if score >= 8.5:
                rec.language_points = 124
            elif score >= 8.0:
                rec.language_points = 116
            elif score >= 7.5:
                rec.language_points = 108
            elif score >= 7.0:
                rec.language_points = 92
            elif score >= 6.5:
                rec.language_points = 80
            elif score >= 6.0:
                rec.language_points = 68
            elif score >= 5.5:
                rec.language_points = 50
            elif score >= 5.0:
                rec.language_points = 38
            else:
                rec.language_points = 0

    @api.depends(
        'age_points', 'education_points', 'work_points', 'language_points',
        'job_offer_points', 'provincial_nomination_points', 
        'education_in_canada_points', 'foreign_work_experience_points',
        'sibling_in_canada_points'
    )
    def _compute_crs_score(self):
        for rec in self:
            rec.crs_score = (
                rec.age_points + rec.education_points + rec.work_points + 
                rec.language_points + rec.job_offer_points + 
                rec.provincial_nomination_points + rec.education_in_canada_points +
                rec.foreign_work_experience_points + rec.sibling_in_canada_points
            )

    @api.depends('crs_score', 'destination_country')
    def _compute_eligibility_score(self):
        for rec in self:
            if rec.destination_country == 'canada':
                # Express Entry cutoff is around 500
                if rec.crs_score >= 600:
                    rec.eligibility_score = rec.crs_score
                elif rec.crs_score >= 450:
                    rec.eligibility_score = rec.crs_score
                else:
                    rec.eligibility_score = rec.crs_score
            else:
                rec.eligibility_score = rec.crs_score

    @api.model
    @api.model
    def create(self, vals_list):
        """Generate sequence for new assessments"""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('amb.assessment') or 'New'
        
        return super().create(vals_list)

    @api.onchange('destination_country', 'program_type')
    def _onchange_program_info(self):
        """Update eligibility based on program type"""
        if self.destination_country == 'canada' and self.program_type == 'pr':
            return {'warning': {
                'title': 'Permanent Residency Program',
                'message': 'CRS scoring will be calculated based on the information you provide.',
            }}

    # === Action Methods ===

    def action_calculate_crs(self):
        """Recalculate CRS score"""
        for assessment in self:
            # Force recompute by writing same values
            assessment.write({
                'age': assessment.age,
                'education_level': assessment.education_level,
                'work_experience_years': assessment.work_experience_years,
            })
            assessment._compute_crs_score()

    def action_update_eligibility(self):
        """Update eligibility status based on CRS score"""
        for assessment in self:
            # if assessment.destination_country == 'canada':
            #     if assessment.crs_score >= 550:
            #         assessment.eligibility_status = 'highly_eligible'
            #     elif assessment.crs_score >= 450:
            #         assessment.eligibility_status = 'eligible'
            #     elif assessment.crs_score >= 300:
            #         assessment.eligibility_status = 'partially_eligible'
            #     else:
            #         assessment.eligibility_status = 'not_eligible'

            if assessment.destination_country == 'canada':
                if assessment.crs_score >= 400:
                    assessment.eligibility_status = 'highly_eligible'
                elif assessment.crs_score >= 350:
                    assessment.eligibility_status = 'eligible'
                elif assessment.crs_score >= 300:
                    assessment.eligibility_status = 'partially_eligible'
                else:
                    assessment.eligibility_status = 'not_eligible'

            else:
                # For other countries, use general scoring
                if assessment.crs_score >= 70:
                    assessment.eligibility_status = 'highly_eligible'
                elif assessment.crs_score >= 50:
                    assessment.eligibility_status = 'eligible'
                elif assessment.crs_score >= 30:
                    assessment.eligibility_status = 'partially_eligible'
                else:
                    assessment.eligibility_status = 'not_eligible'

    def action_mark_in_progress(self):
        """Mark assessment as in progress"""
        for assessment in self:
            assessment.write({'state': 'in_progress'})

    def action_mark_completed(self):
        """Mark assessment as completed"""
        for assessment in self:
            assessment.action_update_eligibility()
            assessment.write({'state': 'completed'})

    def action_generate_report(self):
        """Generate assessment report"""
        self.ensure_one()
        return self.env.ref('amb_crm.action_assessment_report').report_action(self)

    def action_send_to_customer(self):
        """Send assessment to customer"""
        self.ensure_one()
        template = self.env.ref('amb_crm.email_template_assessment_result')
        if template:
            template.send_mail(self.id, force_send=True)
        return {'type': 'ir.actions.act_window_close'}

    def action_add_payment(self):
        """Create payment from assessment with program type pre-filled"""
        self.ensure_one()
        ctx = self.env.context.copy()
        ctx.update({
            'default_opportunity_id': self.opportunity_id.id,
            'default_partner_id': self.partner_id.id,
            'default_assessment_id': self.id,
        })
        # Pass assessment's program_type to payment's program_type
        if self.program_type and self.program_type.id:
            ctx['default_program_type'] = self.program_type.id
            # Also pass the expected amount from program type's list price
            ctx['default_expected_amount'] = self.program_type.list_price or 0.0
        return {
            'name': ('Add Payment'),
            'view_mode': 'form',
            'res_model': 'amb.payment',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': ctx,
        }

    def action_create_invoice(self):
        """Create invoice directly from assessment and link payment"""
        self.ensure_one()
        
        # Validate requirements
        if not self.program_type:
            raise ValidationError('Please select a Program Type before creating an invoice.')
        
        if not self.partner_id:
            raise ValidationError('No customer found for this assessment.')
        
        # Get journal (default sales journal)
        journal_id = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        
        if not journal_id:
            raise ValidationError('Please configure a Sales Journal in Accounting.')
        
        # Get product from program_type
        product_id = self.program_type
        service_name = self.program_type.name or 'Immigration Service'
        price_unit = self.program_type.list_price or 0.0
        
        # Get the revenue account - use product's income account first, then journal default
        revenue_account_id = False
        if product_id:
            revenue_account_id = product_id.property_account_income_id.id
        if not revenue_account_id:
            # Fallback to journal's default account
            revenue_account_id = journal_id.default_account_id.id
        
        # Create invoice line
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
        origin_ref = 'Assessment: %s | %s' % (self.name, self.program_type.name or 'Service')
        
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
        
        # Create linked payment record
        payment_vals = {
            'partner_id': self.partner_id.id,
            'opportunity_id': self.opportunity_id.id,
            'assessment_id': self.id,
            'program_type': self.program_type.id,
            'expected_amount': price_unit,
            'amount': 0.0,  # Initially unpaid
            'state': 'pending',
            'invoice_id': invoice.id,
        }
        
        payment = self.env['amb.payment'].create(payment_vals)
        
        # Return action to open the invoice
        return {
            'name': ('Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }
