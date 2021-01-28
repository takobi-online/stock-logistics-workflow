# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models
from odoo.tools.translate import _


class XlsxStockClosePeriod(models.AbstractModel):
    _name = 'report.stock_close_period.report_xlsx_stock_close_print'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, extra):
        ids = data['ids']
        close_name = data['form']['close_name']

        lines = self.env['stock.close.period.line'].browse(ids)

        sheet = workbook.add_worksheet(_('stock.close.period'))
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.fit_to_pages(1, 0)
        sheet.set_column(0, 0, 20)
        sheet.set_column(1, 1, 50)
        sheet.set_column(2, 2, 50)
        sheet.set_column(3, 3, 15)
        sheet.set_column(4, 4, 15)
        sheet.set_column(5, 5, 10)
        sheet.set_column(6, 6, 15)
        sheet.set_column(7, 7, 20)

        dt10 = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        bold_style = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'bottom': 1})
        title_style = workbook.add_format({'bold': False, 'bg_color': '#C0C0C0', 'bottom': 1})
        currency_format = workbook.add_format({'num_format': '€ #,##0.00'})

        # header
        i = 0
        sheet.write(i, 0, _('Stock Close Period'), bold_style)
        sheet.write(i, 1, close_name, bold_style)

        i += 1
        sheet_title = [_('Product'),
                       _('Name'),
                       _('Category'),
                       _('Evaluation'),
                       _('Quantity'),
                       _('Uom'),
                       _('Unit Cost'),
                       _('Total Cost'),
                       ]
        sheet.write_row(i, 0, sheet_title, title_style)
        i += 1

        # rows
        for row in lines:
            total_price = row.product_qty * row.price_unit
            sheet.write(i, 0, row.product_code or '')
            sheet.write(i, 1, row.product_name or '')
            sheet.write(i, 2, row.categ_name or '')
            sheet.write(i, 3, row.evaluation_method or '')
            sheet.write(i, 4, row.product_qty)
            sheet.write(i, 5, row.product_uom_id.name)
            sheet.write(i, 6, row.price_unit, currency_format)
            sheet.write(i, 7, total_price, currency_format)
            i += 1
        return i
