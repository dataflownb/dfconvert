
import os
from setuptools import setup

# Get location of this file at runtime
HERE = os.path.abspath(os.path.dirname(__file__))

# Eval the version tuple and string from the source
VERSION_NS = {}
with open(os.path.join(HERE, 'dashboards_bundlers/_version.py')) as f:
    exec(f.read(), {}, VERSION_NS)

setup_args = dict(
    name='dfipy_convert',
    author='Dataflow Notebook Team',
    author_email='jupyter@googlegroups.com',
    description='Tool for converting to and from IPykernel/DFKernel Compliant Notebooks',
    long_description='''
    This package adds *Download as* menu items for translating notebooks created using IPykernel or DFKernel to be
    compliant with the alternative Notebook environment.
See `the project README <https://github.com/colinjbrown/dfipy_convert>`_
for more information.
''',
    url='https://github.com/colinjbrown/dfipy_convert',
    version=VERSION_NS['__version__'],
    license='BSD',
    platforms=['Jupyter Notebook 5.x'],
    packages=[
        'dfipy_convert',
    ],
    include_package_data=True,
    install_requires=[
        'redbaron>=0.6',
        'notebook>=5.0'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ]
)

if __name__ == '__main__':
    setup(**setup_args)