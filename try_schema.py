from app.schemas import LeadResult

good = LeadResult(
    name='Dave',
    email='dave@gmail.com',
    category='sales_inquiry',
    priority=4,
    summary='Wants a roof repair quote.',
)
print(good)

try:
    LeadResult(category='banana', priority=9, summary='x')
except Exception as e:
    print(e)