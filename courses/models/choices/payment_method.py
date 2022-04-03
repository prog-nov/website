class PaymentMethod:
    COUNTER = 'counter'
    COURSE = 'course'
    ONLINE = 'online'
    VOUCHER = 'voucher'
    PRICE_REDUCTION = 'reduction'

    CHOICES = (
        (COUNTER, 'counter'),
        (COURSE, 'course'),
        (ONLINE, 'online'),
        (VOUCHER, 'voucher'),
        (PRICE_REDUCTION, 'price reduction')
    )
