# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models, _
from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    # related field to manage closed lines
    active = fields.Boolean(default=True)


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # add field to manage closed lines
    active = fields.Boolean(related="move_id.active", store=True, default=True)

    def _recompute_average_cost_period(self):
        #
        #   20200713 - Marcelo Frare
        #   la logica applicata al presente metodo presuppone che un prodotto segua sempre
        #   la stessa regola di appgovvigionamento:
        #   - di acquisto
        #   - di produzione
        #   - di produzione esterna o di conto lavoro
        #
        #   nel caso dovesse cambiare metodo di approvvigionamento, si deve creare
        #   un codice diverso
        #
        #   per garantire questo principio dovrei bloccare la modifica all'opzione
        #   di modifica al metodo di approvvigionamento  nel caso trovasse movimenti
        #   di magazzino già validati.
        #   Ad oggi il cliente non vuole questo vincolo.
        #

        _logger.info('Recompute average cost period. Making in 3 phases:')
        _logger.info("[1/3] Recompute cost product purchase")
        _logger.info("[2/3] Recompute cost product production")
        _logger.info("[3/3] Write results")

        self._recompute_cost_stock_move_purchase()
        self._add_standard_cost_product()
        self._write_results()

        _logger.info('End recompute average cost product')

    def _recompute_cost_stock_move_purchase(self):
        #
        #   Aquisti: Prezzo medio ponderato nel periodo. Esempio:
        #
        #   data        causale             quantità    prezzo unitario     totale      prezzo medio
        #   01/01/19    giacenza iniziale   9390        3,1886              29940,95
        #   12/04/19    carico da aquisto   8000        3,23                25840,00
        #                                   17390                           55780,95    3,2076
        #


        _logger.info("[1/3] Start recompute average cost product")
        company_id = self.env.user.company_id.id
        wcp = self.env['stock.close.period']
        wcpl = self.env['stock.close.period.line']
        sm = self.env['stock.move']
        ph = self.env['product.price.history']
        mb = self.env['mrp.bom']
        i = 0

        #   get closing_id
        closing_id = wcp.search([('state', '=', 'confirm')], limit=1)
        #   search only lines not elaborated
        closing_line_ids = wcpl.search([
            ('close_id', '=', closing_id.id),
            ('price_unit', '=', 0)
        ])

        # get last_close_date
        last_closed_id = wcp.search(
            [('state', '=', 'done')], order='close_date desc', limit=1)
        if last_closed_id:
            # get from last closed
            last_close_date = last_closed_id.close_date
        else:
            # gel all moves
            last_close_date = '2010-01-01'

        #   all closing_line ready to elaborate
        for closing_line_id in closing_line_ids:
            product_id = closing_line_id.product_id

            #   solo prodotti valutati al medio
            if product_id.categ_id.property_cost_method != 'average':
                continue

            #   counter
            i += 1

            if product_id.default_code:
                _logger.info('[1/3] ' + str(i) + ' - ' + product_id.default_code)
            else:
                _logger.info('[1/3] ' + str(i) + ' - ' + product_id.name)

            # se il prodotto ha una bom, non deve processarlo
            if mb._bom_find(product_id):
                continue

            # recupera i movimenti di magazzino
            move_ids = sm.search([
                ('state', '=', 'done'),
                ('product_qty', '>', 0),
                ('product_id', '=', product_id.id),
                ('date', '>', last_close_date),
                ('active', '>=', 0),
            ], order='date')

            first_move_date = False
            qty = 0
            amount = 0
            new_price = 0
            for move_id in move_ids:

                if not first_move_date:
                    # init new product
                    first_move_date = move_id.date

                    #   cancella lo storico dei prezzi
                    storic_price = ph.search([
                        ('product_id', '=', product_id.id),
                        ('datetime', '>=', first_move_date),
                    ])
                    if storic_price:
                        storic_price.unlink()

                    # get start data from last close
                    start_qty, start_price = self._get_last_closing(product_id.id)

                    # se valorizzata, crea la prima riga sullo storico prezzi
                    if start_qty:
                        ph.create({
                            'product_id': product_id.id,
                            'datetime': first_move_date,
                            'cost': start_price,
                            'company_id': company_id,
                        })

                        # fissa il punto iniziale
                        amount = start_price * start_qty
                        qty = start_qty
                        new_price = start_price

                    else:
                        # se non trova un valore iniziale, imposta il costo al valore
                        # alla data di partenza, altrimenti i movimenti di scarico
                        # rimangono a zero
                        start_price = product_id.get_history_price(company_id, move_id.date)

                        ph.create({
                            'product_id': product_id.id,
                            'datetime': first_move_date,
                            'cost': start_price,
                            'company_id': company_id,
                        })

                        # fissa il punto iniziale
                        amount = 0
                        qty = 0
                        new_price = start_price

                #   si tratta di un acquisto
                if move_id.purchase_line_id:

                    # non dovrebbe capitare, ma esistono righe con PO e WO impostate
                    # sono uscite di magazzino verso il terzista, non deve considerare il PO
                    # e deve portare il price_unit a zero
                    if move_id.workorder_id:
                        move_id.price_unit = 0
                        move_id.value = 0
                        move_id.remaining_value = 0

                    else:
                        # è un vero PO da mediare
                        # fa prevalere vale il prezzo sul PO nel caso sia stato aggiornato
                        price = move_id.purchase_line_id.price_unit
                        if move_id.price_unit != price:
                            new_price = price
                            move_id.price_unit = new_price
                            move_id.value = move_id.product_uom_qty * new_price
                            move_id.remaining_value = move_id.product_uom_qty * new_price

                        #   calculate new ovl price if price > 0
                        if price > 0:
                            qty += move_id.product_qty
                            amount += (move_id.product_qty * price)

                        if qty != 0.0:
                            new_price_ovl = amount / qty
                        else:
                            new_price_ovl = 0

                        if new_price_ovl != new_price:
                            # assegna il nuovo prezzo
                            new_price = new_price_ovl
                            # crea lo storico
                            ph.create({
                                'product_id': move_id.product_id.id,
                                'datetime': move_id.date,
                                'cost': new_price,
                                'company_id': company_id,
                            })

                else:
                    #   imposta su movimento di magazzino il nuovo costo medio ponderato
                    if move_id.price_unit != new_price:
                        # move_id.price_unit = new_price
                        # move_id.value = move_id.ordered_qty * new_price
                        # move_id.remaining_value = move_id.ordered_qty * new_price

                        # fatto con sql altrimenti l'ORM scatena l'inferno
                        value = move_id.product_uom_qty * new_price
                        remaining_value = move_id.product_uom_qty * new_price

                        #   set active = False on stock_move and stock_move_line
                        query = """
                        UPDATE
                            stock_move
                        SET
                            price_unit = %r,
                            value = %r,
                            remaining_value = %r
                        WHERE
                            id = %r;
                        """ % (new_price, value, remaining_value, move_id.id)
                        self.env.cr.execute(query)

                if i % 100 == 0:
                    logging.info(str(i)+' move recomputed')
                    self.env.cr.commit()

            # memorizzo il risultato alla data di chiusura
            closing_line_id.price_unit = product_id.get_history_price(company_id, closing_id.close_date)
            closing_line_id.evaluation_method = 'purchase'

        self.env.cr.commit()
        _logger.info("[1/3] Finish recompute average cost product")

    def _add_standard_cost_product(self):
        #
        #   Produzione INTERNA: Prezzo STANDARD medio ponderato nel periodo.
        #   Produzione ESTERNA: Prezzo STANDARD medio ponderato nel periodo.
        #
        #   il calcolo della media ponderata è uguale che per gli acquisti.
        #   il valore del prodotto è dato da:
        #   → Produzione INTERNA:
        #   + somma dei costi STANDARD dei componenti semilavorati
        #   + somma dei costi STANDARD dei componenti di acqusto
        #
        #   → Produzione ESTERNA:
        #   + somma dei costi STANDARD dei componenti inviati al fornitore
        #   + somma degli acquisto per le lavorazioni eseguite
        #

        _logger.info("[2/3] Start add standard cost product")
        company_id = self.env.user.company_id.id
        wcp = self.env['stock.close.period']
        wcpl = self.env['stock.close.period.line']
        sm = self.env['stock.move']
        mb = self.env['mrp.bom']
        i = 0

        #   get closing_id
        closing_id = wcp.search([('state', '=', 'confirm')], limit=1)

        #   search lines
        wcpl.search([
            ('close_id', '=', closing_id.id),
        ])

        #   search only lines not elaborated
        closing_line_ids = wcpl.search([
            ('close_id', '=', closing_id.id),
            ('price_unit', '=', 0)
        ])

        # imposta il metodo di calcolo
        if closing_id.force_standard_price:
            method = 'standard'
        else:
            method = 'production'

        # get last_close_date
        last_closed_id = wcp.search([('state', '=', 'done')], order='close_date desc', limit=1)
        if last_closed_id:
            # get from last closed
            last_close_date = last_closed_id.close_date
        else:
            # get all moves
            last_close_date = '2010-01-01'

        #   all closing_line_ids ready to elaborate
        for closing_line_id in closing_line_ids:
            product_id = closing_line_id.product_id
            template_id = closing_line_id.product_id.product_tmpl_id
            # solo prodotti valutati allo standard
            if product_id.categ_id.property_cost_method != 'standard':
                continue

            # counter
            i += 1

            if product_id.default_code:
                _logger.info('[2/3] ' + str(i) + ' - ' + product_id.default_code)
            else:
                _logger.info('[2/3] ' + str(i) + ' - ' + product_id.name)

            #   recupera i movimenti di magazzino
            move_ids = sm.search([
                ('state', '=', 'done'),
                ('product_qty', '>', 0),
                ('product_id', '=', product_id.id),
                ('date', '>', last_close_date),
                ('active', '>=', 0),
            ], order='date')

            std_cost = 0.0
            for move_id in move_ids:

                _logger.info('[2/3] move id: ' + str(move_id))

                # ricalcola std_cost considerando solo i versamenti di produzione
                # verso il magazzino prinipale.
                # _todo_:
                #   sostituire il 15 con il codice del magazzino azienda
                if move_id.location_dest_id.id == 15 or std_cost == 0:
                    if closing_id.force_standard_price:
                        # recupera il prezzo standard alla data del movimento
                        std_cost = product_id.get_history_price(company_id, move_id.date)
                    else:
                        # recupero il costo industriale della BOM [costo standard bom]
                        bom = mb._bom_find(template_id)
                        if bom:
                            # standard bom cost at date
                            node = bom.get_bom_cost(move_id.date)
                            std_cost = round(node['product_cost2'], 5)

                    # se non trova std_cost, prende il prezzo ora disponibile
                    if std_cost == 0:
                        std_cost = product_id.standard_price

                # imposta su movimento di magazzino il nuovo costo medio ponderato
                if move_id.price_unit != std_cost:
                    # fatto con sql altrimenti l'ORM scatena l'inferno
                    value = move_id.product_uom_qty * std_cost
                    remaining_value = move_id.product_uom_qty * std_cost

                    #   set active = False on stock_move and stock_move_line
                    query = """
                    UPDATE
                        stock_move
                    SET
                        price_unit = %r,
                        value = %r,
                        remaining_value = %r
                    WHERE
                        id = %r;
                    """ % (std_cost, value, remaining_value, move_id.id)
                    self.env.cr.execute(query)

            # memorizzo il risultato
            # recupero il prezzo standard dallo storico alla data di chisura
            # TODO https://github.com/marcelofrare/stock-logistics-workflow/commit/a2790a12047ca96a7c25dfa2e6dcb384e15b13f1#r46518838
            price_unit = product_id.get_history_price(company_id, closing_id.close_date)
            # oppure il prezzo attuale se non trovo lo storico
            if price_unit == 0:
                price_unit = product_id.standard_price

            closing_line_id.price_unit = price_unit
            closing_line_id.evaluation_method = method

        self.env.cr.commit()
        _logger.info("[2/3] Finish add standard cost product")

    def _write_results(self):

        wcp = self.env['stock.close.period']
        wcpl = self.env['stock.close.period.line']
        decimal = dp.get_precision('Product Price')(self._cr)[1]

        #   get closing_id
        closing_id = wcp.search([('state', '=', 'confirm')], limit=1)

        #   search lines
        closing_line_ids = wcpl.search([
            ('close_id', '=', closing_id.id),
        ])

        _logger.info("[3/3] Start writing results")

        #   all closing_line_ids ready to elaborate
        amount = 0
        for closing_line_id in closing_line_ids:
            # calcolo totale per riga
            row_value = closing_line_id.product_qty * closing_line_id.price_unit
            amount += round(row_value, decimal)

        # set amount closing
        closing_id.amount = amount

        # delete all line with product_qty = 0
        query = """
            DELETE FROM
                stock_close_period_line
            WHERE
                close_id = %r and product_qty = 0;
            """ % (closing_id.id)
        self.env.cr.execute(query)

        _logger.info("[3/3] Finish writing results")

    def _get_last_closing(self, product_id):
        wcp = self.env['stock.close.period']
        wcpl = self.env['stock.close.period.line']

        #   dafault value
        start_qty = 0
        start_price = 0

        #   get last closing_id
        closing_id = wcp.search([('state', '=', 'done')], order='close_date desc', limit=1)
        #   search product
        closing_line_id = wcpl.search([
            ('close_id', '=', closing_id.id),
            ('product_id' , '=', product_id)
        ], limit=1)

        if closing_line_id:
            start_qty = closing_line_id.product_qty
            start_price = closing_line_id.price_unit

        return start_qty, start_price
