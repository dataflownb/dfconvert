import dfconvert.make_dfpy as dfpy
from dfconvert.constants import DF_CELL_PREFIX
import ast
import astor
import nbformat

def test_transform():
    assert dfpy.transform('Out_aaaaaa') == 'Out[aaaaaa]'

def test_comment_remove():
    content = 'a=2\na+3\n'
    cell = DF_CELL_PREFIX+content+DF_CELL_PREFIX
    assert dfpy.remove_comment(cell) == content


def test_last_node_trans():
    assert astor.to_source(dfpy.transform_last_node(ast.parse('Out_aaaaaa = 2').body[-1])) == '2\n'
    assert astor.to_source(dfpy.transform_last_node(ast.parse('Out_aaaaaa, Out_bbbbbb = 2,3').body[-1])) == '2, 3\n'


def test_valid_nb():
    fname = 'digits-classification-df'
    ext = '_ipy.ipynb'
    nb = nbformat.read('./dfconvert/tests/example/'+fname+ext,nbformat.NO_CONVERT)
    dfpy.import_dfpynb(fname+ext,nb)
    new_nb = nbformat.read('./'+fname+'_dfpy.ipynb',nbformat.NO_CONVERT)
    #Test will fail if this notebook does not validate
    #Upon a validation failure nbformat will raise a ValidationError
    nbformat.validate(new_nb)
