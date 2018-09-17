# dfconvert

This is a library provided in the form of a bundler extension that allows the conversion of normal IPython notebooks into their Dataflow equivalents and back again to provide a proper roundtrip. There is no guarantee made that the Notebook that enters will be the same exact Notebook but it should perform in the same way.

A topological sort if also applied to the Notebook to ensure that it can be ran top down.

It relies on IPython core methods for some of the translation process so some magic and system commands may be translated into their IPython equivalent.

## Installation Instructions

1. cd to outer `dfconvert` that contains `setup.py`.
2. `pip install .`
3. `jupyter bundlerextension enable --sys-prefix --py dfconvert`
