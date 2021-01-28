# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import logging
from datetime import datetime
logger = logging.getLogger(__name__)


class StockClosePeriod(models.Model):
    _name = "stock.close.period"
    _description = "Stock Close Period"

    name = fields.Char(
        'Reference',
        readonly=True, required=True,
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    line_ids = fields.One2many(
        'stock.close.period.line', 'close_id', string='Product',
        copy=True, readonly=False,
        states={'done': [('readonly', True)]})
    state = fields.Selection(string='Status', selection=[
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('confirm', 'In Progress'),
        ('done', 'Validated')],
        copy=False, index=True, readonly=True,
        default='draft')
    close_date = fields.Date(
        'Close Date',
        readonly=True, required=True,
        default=fields.Date.today,
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]},
        help="The date that will be used for the store the product quantity "
             "and average cost.")
    amount = fields.Float(
        string="Stock Amount Value",
        readonly=True,
        copy=False,)
    work_start = fields.Datetime(
        'Work Start',
        readonly=True,
        default = fields.Datetime.now)
    work_end = fields.Datetime(
        'Work End',
        readonly=True)
    force_standard_price = fields.Boolean(
        default=False,
        help="Forces the use of the standard price instead of calculating the cost "
             "from the BOM.")
    force_archive = fields.Boolean(
        default=False,
        help="Marks as archive the inventory move lines used during the process.")

    @api.model
    def create(self, values):
        if self._check_existing():
            closing_id = False
        else:
            closing_id = super(StockClosePeriod, self).create(values)
        return closing_id

    def _check_existing(self):
        existings = self.search([('state', '=', 'confirm')])
        if existings:
            raise UserError(_(
                "You cannot have two stock closing in state 'in Progress'"))
        return existings

    def action_set_to_draft(self):
        if self.state == 'cancel':
            #   clear data
            wcpl = self.env['stock.close.period.line'].search(
                [('close_id', '=', self.id)])
            if wcpl:
                wcpl.unlink()
            self.state = 'draft'

    def action_start(self):
        if not self._check_existing():
            for closing in self.filtered(lambda x: x.state not in ('done', 'cancel')):
                # add product line
                closing._get_product_lines()
                # set confirm status
                self.state = 'confirm'
        return True

    def _get_product_lines(self):
        #   add all active products, not service type
        # TODO multi company
        query = """
            INSERT INTO stock_close_period_line(close_id, product_id, product_code,
            product_name, product_uom_id, categ_name, product_qty, price_unit)
            SELECT
              %r as close_id,
              product_product.id as product_id,
              product_template.default_code as product_code,
              product_template.name as product_name,
              product_template.uom_id as product_uom,
              product_category.complete_name as complete_name,
              0 as product_qty,
              0 as price_unit
            FROM
              product_template,
              product_product,
              product_category
            WHERE
              product_template.type != 'service' and
              product_product.product_tmpl_id = product_template.id and
              product_template.categ_id = product_category.id
            ORDER BY
                product_product.id;
            """ % self.id

        self.env.cr.execute(query)

        # get quantity on end period for each product
        closing_line_ids = self.env['stock.close.period.line'].search([
            ('close_id', '=', self.id)])

        for closing_line_id in closing_line_ids:
            # giacenza fine periodo
            product_id = closing_line_id.product_id
            product_qty = product_id._compute_qty_available(self.close_date)
            closing_line_id.product_qty = product_qty

    def action_done(self):
        if not self._check_qty_available():
            raise UserError(
                _("Is not possible continue the execution. There are product with "
                  "quantities < 0."))

        self._average_price_recalculate()
        if self.force_archive:
            self._deactivate_moves()
        self.state = 'done'
        self.work_end = datetime.now()
        return True

    def _check_qty_available(self):
        # if a negative value, can't continue
        negative = self.env['stock.close.period.line'].search([
            ('close_id', '=', self.id),
            ('product_qty', '<', 0)
             ])
        if negative:
            res = False
        else:
            res = True
        return res

    def _average_price_recalculate(self):
        self.env['stock.move.line']._recompute_average_cost_period()
        return True

    def _deactivate_moves(self):
        #   set active = False on stock_move and stock_move_line
        # TODO multi company
        query = """
        UPDATE
            stock_move
        SET
            active = false
        WHERE
            date <= date(%r) and state = 'done';
        """ % self.close_date
        self.env.cr.execute(query)

        # TODO multi company
        query = """
        UPDATE
            stock_move_line
        SET
            active = false
        WHERE
            date <= date(%r) and state = 'done';
        """ % self.close_date
        self.env.cr.execute(query)

        return True


class StockClosePeriodLine(models.Model):
    _name = "stock.close.period.line"
    _description = "Stock Close Period Line"

    close_id = fields.Many2one(
        'stock.close.period', 'Stock Close Period',
        index=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', '=', 'product')],
        index=True, required=True)
    product_name = fields.Char(
        'Product Name', related='product_id.name', store=True, readonly=True)
    product_code = fields.Char(
        'Product Code', related='product_id.default_code', store=True, readonly=True)
    product_uom_id = fields.Many2one(
        'uom.uom', 'UOM',
        required=True,
        default=lambda self: self.env.ref('uom.product_uom_unit',
                                          raise_if_not_found=True))
    categ_name = fields.Char(
        'Category Name', related='product_id.categ_id.complete_name', store=True,
        readonly=True)
    evaluation_method = fields.Selection(string='Evaluation method', selection=[
        ('purchase', _('Purchase')),
        ('standard', _('Standard')),
        ('production', _('Production'))],
        copy=False)
    product_qty = fields.Float(
        'End Quantity',
        digits=dp.get_precision('Product Unit of Measure'),
        default=0)
    price_unit = fields.Float(
        string='End Average Price', digits=dp.get_precision('Product Price'))

