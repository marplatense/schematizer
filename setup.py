try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

requires = [
    "sqlalchemy>=0.9",
    "colander",
    "deform",
    "webtest",
    "cornice",
    "python-dateutil"
    ]
config = {
    'description': 'sqlalchemy-to-colander and back',
    'author': 'Mariano Mara',
    'url': 'https://github.com/marplatense/schematizer',
    'download_url': 'https://github.com/marplatense/schematizer/archive/master.zip',
    'author_email': 'mariano.mara@gmail.com'
    'version': '0.1',
    'install_requires': requires,
    'packages': ['schematizer'],
    'scripts': [],
    'name': 'Schematizer'
}

setup(requires=['colander','sqlalchemy>=0.9', 'colander', 'deform', 'webtest', 'cornice', 'python-dateutil'], **config)
