# Copyright 2020 Marcelo Frare (Associazione PNLUG - Gruppo Odoo)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Stock Close Period',
    'summary': 'Weighted average cost method for inventory valuation',
    'version': '12.0.1.0.0',
    'category': 'Stock',
    'author': 'Pordenone Linux User Group (PNLUG), Odoo Community Association (OCA)',
    'maintainers': ["marcelofrare", "andreampiovesana"],
    'website': 'https://github.com/OCA/stock-logistics-workflow',
    'license': 'AGPL-3',
    'depends': [
        'product_price_history',
        'stock',
        'mrp',  # TODO bridge module adding mrp functionalities
        'report_xlsx',
        # 'purchase_discount', TODO evaluate bridge module
    ],
    'external_dependencies': {
        'python': [
            'unicodecsv'
        ],
    },
    'data': [
        'views/stock_close_views.xml',
        'wizards/stock_close_import.xml',
        'wizards/stock_close_print.xml',
        'reports/xlsx_stock_close_print.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
