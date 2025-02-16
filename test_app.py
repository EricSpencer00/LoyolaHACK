import unittest
from app import app

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_realtime_bus(self):
        response = self.app.get('/api/realtime?type=bus')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)  # Assuming get_cta_bus_data() returns a list

    def test_realtime_train(self):
        response = self.app.get('/api/realtime?type=train')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)  # Assuming get_cta_train_data() returns a list

    def test_realtime_invalid_type(self):
        response = self.app.get('/api/realtime?type=invalid')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data['error'], 'Invalid transit type')

    def test_index_authenticated(self):
        with self.app.session_transaction() as sess:
            sess['authenticated'] = True
        response = self.app.get('/')
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard

    def test_index_not_authenticated(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'signin.html', response.data)

if __name__ == '__main__':
    unittest.main()