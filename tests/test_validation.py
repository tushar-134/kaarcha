import os
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app

class ValidationTests(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp();os.close(fd)
        self.client=create_app(self.path).test_client()
        self.client.post('/api/v1/members',json={'name':'A'})
        self.client.post('/api/v1/members',json={'name':'B'})
    def tearDown(self):os.unlink(self.path)
    def test_bad_json_shapes_are_400(self):
        for endpoint in ('members','expenses'):
            for body in ([],['x'],False,2,'str',None):
                with self.subTest(endpoint=endpoint,body=body):
                    res=self.client.post('/api/v1/'+endpoint,json=body)
                    self.assertEqual(res.status_code,400)
                    self.assertIn('error',res.get_json())
    def test_expense_malformed_fields_never_500(self):
        base={'description':'x','amount_paise':100,'paid_by':1}
        cases=[{'description':42},{'description':['x']},{'amount_paise':True},{'amount_paise':1.5},
               {'amount_paise':10**30},{'paid_by':True},{'date':'2026-02-30'},{'date':25},
               {'split':[]},{'split':{'type':'equal','member_ids':[]}},
               {'split':{'type':'equal','member_ids':[{}]}},
               {'split':{'type':'equal','member_ids':[True]}},
               {'split':{'type':'equal','member_ids':[1,1]}},
               {'split':{'type':'exact','shares':[1]}},
               {'split':{'type':'exact','shares':[{'member_id':True,'amount_paise':100}]}}]
        for override in cases:
            with self.subTest(override=override):
                res=self.client.post('/api/v1/expenses',json={**base,**override})
                self.assertEqual(res.status_code,400)
                self.assertIn('error',res.get_json())
        self.assertEqual(self.client.get('/api/v1/expenses').get_json()['expenses'],[])
    def test_http_errors_json_and_actual_ui_served(self):
        for url in ('/api/v1/nonexistent','/api/v1/expenses/999'):
            res=self.client.get(url);self.assertEqual(res.status_code,404);self.assertIn('error',res.get_json())
        res=self.client.get('/');self.assertEqual(res.status_code,200);res.close()
        for file in ('api.js','app.js','styles.css'):
            res=self.client.get('/'+file);self.assertEqual(res.status_code,200);res.close()
