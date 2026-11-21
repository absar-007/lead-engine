from app.db import init_db
from app.service import process_lead

init_db()

msg = 'hey need a quote 4 roof repair, call me after 5. Dave'
variants = [msg, msg, msg.upper() + '   ']

for text in variants:
    r = process_lead(text)
    print('id:', r['id'], '| duplicate:', r['duplicate'], '| status:', r['status'], '| cost: $', round(r['cost_usd'], 6))