import dfconvert.make_ipy as ipy
from dfconvert.constants import IPY_CELL_PREFIX
import nbformat
import asttokens

files = ['topology-test']
file_answers = {'topology-test':[10,20,60,110]}


def test_comment_remove():
    content = 'a=2\na+3\n'
    cell = IPY_CELL_PREFIX+content+IPY_CELL_PREFIX
    assert ipy.remove_comment(cell) == content

def test_last_node_trans():
    csource = 'a = 4\na,3,4'
    cast = asttokens.ASTTokens(csource, parse=True)
    exec_count = 40000
    assert ipy.transform_last_node(csource,cast,exec_count) == 'a = 4\nOut_009c40 = []\na, Out_009c40[1], Out_009c40[2] = a, 3, 4\n'
    exec_count = '009c40'
    assert ipy.transform_last_node(csource,cast,exec_count) == 'a = 4\nOut_009c40 = []\na, Out_009c40[1], Out_009c40[2] = a, 3, 4\n'

def test_out_refs():
    csource = 'a = 14\nOut[aaaaaa] = 4\nd=80\nOut["bbbbbb"] = 5\nOut[\'cccccc\'] = 10\na+40'
    cast = asttokens.ASTTokens(csource,parse=True)
    assert ipy.transform_out_refs(csource,cast) == 'a = 14\nOut_aaaaaa = 4\nd=80\nOut_bbbbbb = 5\nOut_cccccc = 10\na+40'

def test_valid_nb():
    """Should only need to test a single Notebook for validity, this is exclusively a validity test"""
    fname = 'digits-classification-df'
    ext = '.ipynb'
    nb = nbformat.read('./dfconvert/tests/example/'+fname+ext,nbformat.NO_CONVERT)
    ipy.export_dfpynb(nb,in_fname=fname+ext)
    new_nb = nbformat.read('./'+fname+'_ipy.ipynb',nbformat.NO_CONVERT)
    #Test will fail if this notebook does not validate
    #Upon a validation failure nbformat will raise a ValidationError
    nbformat.validate(new_nb)


def test_execute_produced_nb():
    """Converts all files inside of the files list, this is a nessecary pre-step for test_compare_results"""
    from nbconvert.preprocessors import ExecutePreprocessor
    ext = '.ipynb'
    for fname in files:
        nb = nbformat.read('./dfconvert/tests/example/' + fname + ext, nbformat.NO_CONVERT)
        ipy.export_dfpynb(nb, in_fname=fname + ext)
        new_nb = nbformat.read('./' + fname + '_ipy.ipynb', nbformat.NO_CONVERT)
        # This is code that createse and executes the topological test to confirm the correct topology is created
        # This should only generally fail if something is changed about nbconvert
        ep = ExecutePreprocessor(timeout=30)
        out = ep.preprocess(new_nb, {'metadata': {'path': ''}})
        with open('./'+fname+'_ipy.ipynb','wt') as f:
            nbformat.write(new_nb,f)

def test_compare_results():
    """Compares the results of our knowns to the re-executed results in ipykernel,
    correct answers are in file_answers dict"""
    for fname in files:
        with open('./'+fname+'_ipy.ipynb','r') as f:
            nb = nbformat.read(f,nbformat.NO_CONVERT)
            answers = file_answers[fname]
            #Ignore last cell because it's empty
            for num, cell in enumerate(nb['cells'][:-1]):
                #Check the first output and compare it to our known values
                #will need to be changed if multiple objects are output
                assert int(cell['outputs'][0]['data']['text/plain']) == answers[num]