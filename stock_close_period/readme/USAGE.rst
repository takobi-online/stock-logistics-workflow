**Inventory → Stock Close Period**

**Stock Close Import**

consente impostare un punto iniziale per recuperare una situazione già esistente
(seguire il tracciato del file di esempio fornito nella cartella example)

**Stock Close Period**

Wizard principale che esegue il calcolo

*FASE 1*:

Si deve indicare il **nome** e la **data di chiusura**

Se attivo il flag **Force Standard Price**, significa che per i prodotti di **PRODUZIONE** il prezzo lo prenderà dal valore impostato sul prezzo standard sulla scheda del prodotto, se invece è spento, lo calcolerà dalla distinta base del prodotto.

Se attivo il flag **Force Archive** significa che alla fine della elaborazione verranno archiviate le righe di movimento di magazzino (stock.move.line)

Lo stato del wizard è ‘draft’
poi si clicca **SAVE** e **START**

Il sistema andrà a popolare le righe con i prodotti presenti e la giacenza alla data di chiusura

Lo stato del wizard è passato a ‘confirm’

*FASE 2*:

In questo momento è possibile modificare le righe presenti intervenendo manualmente sulla giacenza, l’aggiunta o la eliminazione delle righe.

Non sono ammesse giacenze negative

Cliccando su **VALIDA** si da inizio al calcolo

La durata del processo di ricalcolo dipende dal numero di prodotti e dai movimenti presenti

*CONCLUSIONE*

Alla fine del processo lo stato del wizard è passato a ‘validate’, saranno presenti i valori per ogni riga e compilato **Stock Amount Value** con il valore complessivo del magazzino.

**Stock Close Print**

Permette estrarre una situazione consolidata di magazzino in formato xlsx
