import decimal
import unittest

import colander
from sqlalchemy import (
    create_engine,
    Column, Integer, String, DateTime, Numeric, Text
    )
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from schematizer import Schematizer


class SimpleModelTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine('sqlite:///:memory:')
        session = sessionmaker(bind=engine)
        self.session = session()
        base = declarative_base()

        class Basic(base):
            __tablename__ = "basic"
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(100), unique=True, nullable=False)
            sdate = Column(DateTime, nullable=False)
            edate = Column(DateTime)
            value = Column(Numeric, nullable=False,
                           info={'colander': dict(validators=colander.Range(decimal.Decimal('0.01'),
                                                                            decimal.Decimal('9.99')))})
            memo = Column(Text)
            schema = Schematizer(self)
        self.basic = Basic

    def test_basic_attr(self):

        pass



