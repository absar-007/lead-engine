from app.airtable_sync import upsert_lead

fp = 'test-fingerprint-123'

upsert_lead(fp, {'name': 'Test Person', 'category': 'sales_inquiry', 'priority': 3,
                 'summary': 'First version', 'needs_human': False})
print('sent first')

upsert_lead(fp, {'name': 'Test Person', 'category': 'sales_inquiry', 'priority': 4,
                 'summary': 'Second version', 'needs_human': True})
print('sent second')