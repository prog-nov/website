import grpc

from proto.vseth.sip.payment.payment_pb2_grpc import *

from tq_website.settings import PAYMENT_API_HOST, PAYMENT_API_PORT, PAYMENT_API_USE_TLS, PAYMENT_API_WEBURL


class VsethPaymentService:

    def __init__(self) -> None:
        host = f'{PAYMENT_API_HOST}:{PAYMENT_API_PORT}'
        channel = grpc.insecure_channel(host)

        self.payment_stub = PaymentStub(channel)

    def create_order(self):
        pass



