"""test_request.py"""
from unittest import TestCase, main
import logging

from functools import partial

from jsonrpcserver.request import Request
from jsonrpcserver.response import (
    ErrorResponse, RequestResponse, NotificationResponse)
from jsonrpcserver.exceptions import InvalidParams, MethodNotFound
from jsonrpcserver.methods import Methods
from jsonrpcserver import status
from jsonrpcserver import config


def setUpModule():
    config.debug = True

def tearDownModule():
    config.debug = False


# Some dummy functions to use for testing
def foo():
    return 'bar'

class FooClass():
    def foo(self):
        return 'bar'


class TestRequestInit(TestCase):

    def tearDown(self):
        config.convert_camel_case = False

    def test_invalid_request(self):
        req = Request({'jsonrpc': '2.0'})
        self.assertIsInstance(req.response, ErrorResponse)

    def test_ok(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo'})
        self.assertEqual('foo', req.method_name)

    def test_positional_args(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'params': [2, 3]})
        self.assertEqual([2, 3], req.args)

    def test_keyword_args(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'params': {'foo': 'bar'}})
        self.assertEqual({'foo': 'bar'}, req.kwargs)

    def test_request_id(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 99})
        self.assertEqual(99, req.request_id)

    def test_request_id_notification(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo'})
        self.assertEqual(None, req.request_id)

    def test_convert_camel_case(self):
        config.convert_camel_case = True
        req = Request({'jsonrpc': '2.0', 'method': 'fooMethod', 'params': {
            'fooParam': 1, 'aDict': {'barParam': 1}}})
        self.assertEqual('foo_method', req.method_name)
        self.assertEqual({'foo_param': 1, 'a_dict': {'bar_param': 1}}, req.kwargs)

    def test_positional_args_convert_case_skip(self):
        config.convert_camel_case = True
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'params': ['Camel', 'Case']})
        self.assertEqual(['Camel', 'Case'], req.args)


class TestRequestIsNotification(TestCase):

    def test_true(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo'})
        self.assertTrue(req.is_notification)

    def test_false(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 99})
        self.assertFalse(req.is_notification)


class TestCall(TestCase):

    def test_list_functions(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 1})
        self.assertEqual('bar', req.call([foo])['result'])

    def test_list_lambdas(self):
        foo = lambda: 'bar'
        foo.__name__ = 'foo'
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 1})
        self.assertEqual('bar', req.call([foo])['result'])

    def test_list_partials(self):
        multiply = lambda x, y: x * y
        double = partial(multiply, 2)
        double.__name__ = 'double'
        req = Request({'jsonrpc': '2.0', 'method': 'double', 'params': [3], 'id': 1})
        self.assertEqual(6, req.call([double])['result'])

    def test_dict_functions(self):
        req = Request({'jsonrpc': '2.0', 'method': 'baz', 'id': 1})
        self.assertEqual('bar', req.call({'baz': foo})['result'])

    def test_dict_lambdas(self):
        req = Request({'jsonrpc': '2.0', 'method': 'baz', 'id': 1})
        self.assertEqual('bar', req.call({'baz': lambda: 'bar'})['result'])

    def test_dict_partials(self):
        multiply = lambda x, y: x * y
        req = Request({'jsonrpc': '2.0', 'method': 'baz', 'params': [3], 'id': 1})
        self.assertEqual(6, req.call({'baz': partial(multiply, 2)})['result'])

    def test_methods_functions(self):
        methods = Methods()
        methods.add(foo)
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 1})
        self.assertEqual('bar', req.call(methods)['result'])

    def test_methods_functions_with_decorator(self):
        methods = Methods()
        @methods.add
        def foo():
            return 'bar'
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 1})
        self.assertEqual('bar', req.call(methods)['result'])

    def test_methods_lambdas(self):
        methods = Methods()
        methods.add(lambda: 'bar', 'foo')
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 1})
        self.assertEqual('bar', req.call(methods)['result'])

    def test_methods_partials(self):
        multiply = lambda x, y: x * y
        double = partial(multiply, 2)
        methods = Methods()
        methods.add(double, 'double')
        req = Request({'jsonrpc': '2.0', 'method': 'double', 'params': [3], 'id': 1})
        self.assertEqual(6, req.call(methods)['result'])

    def test_positionals(self):
        methods = Methods()
        methods.add(lambda x: x * x, 'square')
        req = Request({'jsonrpc': '2.0', 'method': 'square', 'params': [3], 'id': 1})
        self.assertEqual(9, req.call(methods)['result'])

    def test_keywords(self):
        def get_name(**kwargs):
            return kwargs['name']
        req = Request({'jsonrpc': '2.0', 'method': 'get_name', 'params':
                       {'name': 'foo'}, 'id': 1})
        self.assertEqual('foo', req.call([get_name])['result'])


class TestRequestProcessNotifications(TestCase):
    """Go easy here, no need to test the call function"""

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        config.notification_errors = False

    # Success
    def test_success(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo'}).call([foo])
        self.assertIsInstance(req, NotificationResponse)

    def test_method_not_found(self):
        req = Request({'jsonrpc': '2.0', 'method': 'baz'}).call([foo])
        self.assertIsInstance(req, NotificationResponse)

    def test_invalid_params(self):
        def foo(bar):
            return 'bar'
        req = Request({'jsonrpc': '2.0', 'method': 'foo'}).call([foo])
        self.assertIsInstance(req, NotificationResponse)

    def test_explicitly_raised_exception(self):
        def foo():
            raise InvalidParams()
        req = Request({'jsonrpc': '2.0', 'method': 'foo'}).call([foo])
        self.assertIsInstance(req, NotificationResponse)

    def test_uncaught_exception(self):
        def foo():
            return 1/0
        req = Request({'jsonrpc': '2.0', 'method': 'foo'}).call([foo])
        self.assertIsInstance(req, NotificationResponse)

    # Configuration
    def test_config_notification_errors_on(self):
        # Should return "method not found" error
        request = Request({'jsonrpc': '2.0', 'method': 'baz'})
        config.notification_errors = True
        req = request.call([foo])
        self.assertIsInstance(req, ErrorResponse)

    def test_configuring_http_status(self):
        NotificationResponse.http_status = status.HTTP_OK
        req = Request({'jsonrpc': '2.0', 'method': 'foo'}).call([foo])
        self.assertEqual(status.HTTP_OK, req.http_status)
        NotificationResponse.http_status = status.HTTP_NO_CONTENT


class TestRequestProcessRequests(TestCase):
    """Go easy here, no need to test the call function"""

    # Success
    def test(self):
        req = Request({'jsonrpc': '2.0', 'method': 'foo', 'id': 1}).call([foo])
        self.assertIsInstance(req, RequestResponse)
        self.assertEqual('bar', req['result'])


if __name__ == '__main__':
    main()