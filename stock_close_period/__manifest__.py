# Copyright 2020 Marcelo Frare (Associazione PNLUG - Gruppo Odoo)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Stock Close Period',
    'summary': 'Stock Close Period',
    'version': '11.0.2.0.0',
    'category': 'Stock',
    'author': 'Pordenone Linux User Group (PNLUG), Odoo Community Association (OCA)',
    'website': 'https://github.com/OCA/stock-logistics-workflow',
    'license': 'AGPL-3',
    'depends': [
        'product_price_history',
        'stock',
        'mrp_bom_structure_report',
    ],
    'data': [
        'views/stock_close_views.xml',
        'wizards/stock_close_import.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
