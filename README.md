# dfconvert

[![PyPI version](https://badge.fury.io/py/dfconvert.svg)](https://badge.fury.io/py/dfconvert)
[![Build Status](https://travis-ci.org/dataflownb/dfconvert.svg?branch=beta-update)](https://travis-ci.org/dataflownb/dfconvert)

This is a library provided in the form of a bundler extension that allows the conversion of Dataflow notebooks into their IPykernel equivalents. There is no guarantee made that the Notebook that enters will be as efficient as the notebook in the Dfkernel but it will perform in the same way.

A topological sort if also applied to the Notebook to ensure that it can be ran top down.

It relies on IPython core methods for some of the translation process so some magic and system commands may be translated into their IPython equivalent.

## Installation Instructions

1. cd to outer `dfconvert` that contains `setup.py`.
2. `pip install .`
3. `jupyter bundlerextension enable --sys-prefix --py dfconvert`


### Usage
By enabling the bundler extension you will have the option inside of the File -> Download As method which provides two functions Ipykernel Compatible Notebook.

Optionally the package can also be called by the use of
```
import dfconvert.make_ipy as ipy
file_name = 'mynotebook.ipynb'
nb = nbformat.read(file_name,nbformat.NO_CONVERT)
new_file_name = 'mynewnotebook.ipynb'
dfpy.export_dfpynb(nb, in_fname=file_name, out_fname=new_file_name, md_above=True,full_transform=False,out_mode=False)
```

This will create a notebook with `out_fname` as an ipykernel compatible notebook if `out_fname` is not set then a file will be created with `file_name` that includes a `_dfpy` before the extension to ensure that files do not become overwritten. `md_above` is a flag for marking markdown cells at the top of the notebook and sending the `full_transform` flag set to true will also convert all `Out[aaaaaa]` style references including those that are inside of comments and inside of strings, by default this set to off. `out_mode` is an additional flag that will make sure that if a cell has any output that is normally created in the dfkernel that this output will be shown in a new cell in the `ipykernel`, this will be repeated for all results found in a tuple. 
