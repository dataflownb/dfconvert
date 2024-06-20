import dfconvert.make_ipy as ipy
from dfconvert.export import convert_dfnotebook
import nbformat
import asttokens
import os.path

#file_answers is for topological maps all answers are always in a toplogical order
#maps on the other hand can be in any order and will fail otherwise
file_answers = {'topology-test':[10,20,60,110]}
map_files = ['named_vars','mappings','tag_flag_test']
maps = {}
files = list(file_answers) + list(maps)

def test_last_node_trans():
    csource = 'a = 4\na,3,4'
    cast = asttokens.ASTTokens(csource, parse=True)
    exec_count = 40000
    assert repr(ipy.transform_last_node(csource,cast,exec_count)) == repr('a = 4\nOut_009c40 = [a, 3, 4]\na, Out_009c40[1], Out_009c40[2] = a, 3, 4\n')
    exec_count = '009c40'
    cast = asttokens.ASTTokens(csource, parse=True)
    assert repr(ipy.transform_last_node(csource,cast,exec_count)) == repr('a = 4\nOut_009c40 = [a, 3, 4]\na, Out_009c40[1], Out_009c40[2] = a, 3, 4\n')

def test_out_refs():
    csource = 'a = 14\nOut[aaaaaaaa] = 4\nd=80\nOut["bbbbbbbb"] = 5\nOut[\'cccccccc\'] = 10\na+40'
    cast = asttokens.ASTTokens(csource,parse=True)
    assert ipy.transform_out_refs(csource,cast) == 'a = 14\nOut_aaaaaaaa = 4\nd=80\nOut_bbbbbbbb = 5\nOut_cccccccc = 10\na+40'

def test_valid_nb():
    """Should only need to test a single Notebook for validity, this is exclusively a validity test"""
    fname = 'digits-classification-df'
    ext = '.ipynb'
    nb = nbformat.read(os.path.join('./dfconvert/tests/example/',fname+ext),nbformat.NO_CONVERT)
    convert_dfnotebook(nb,in_fname=fname+ext)
    new_nb = nbformat.read(os.path.join('./',fname+'_ipy.ipynb'),nbformat.NO_CONVERT)
    #Test will fail if this notebook does not validate
    #Upon a validation failure nbformat will raise a ValidationError
    nbformat.validate(new_nb)

def test_execute_produced_nb():
    """Converts all files inside of the files list, this is a nessecary pre-step for test_compare_results"""
    from nbconvert.preprocessors import ExecutePreprocessor
    ext = '.ipynb'
    for fname in files:
        nb = nbformat.read(os.path.join('./dfconvert/tests/example/',fname + ext), nbformat.NO_CONVERT)
        if(fname in map_files):
            maps[fname] = []
            for cell in nb['cells']:
                if 'output' in cell:
                    for out in cell['outputs']:
                        maps[fname].append(out['data']['text/plain'])
        convert_dfnotebook(nb, in_fname=fname + ext,out_mode=True)
        new_nb = nbformat.read(os.path.join('./', fname + '_ipy.ipynb'), nbformat.NO_CONVERT)
        # This is code that createse and executes the topological test to confirm the correct topology is created
        # This should only generally fail if something is changed about nbconvert
        ep = ExecutePreprocessor(timeout=30)
        out = ep.preprocess(new_nb, {'metadata': {'path': ''}})
        with open(os.path.join('./',fname+'_ipy.ipynb'),'wt') as f:
            nbformat.write(new_nb,f)

def test_compare_results():
    """Compares the results of our knowns to the re-executed results in ipykernel,
    correct answers are in file_answers dict"""
    for fname in file_answers.keys():
        with open(os.path.join('./',fname+'_ipy.ipynb'),'r') as f:
            nb = nbformat.read(f,nbformat.NO_CONVERT)
            answers = iter(file_answers[fname])
            #Ignore last cell because it's empty
            for cell in enumerate(nb['cells']):
                if 'outputs' in cell and len(cell['outputs']):
                    #Check the first output and compare it to our known values
                    #will need to be changed if multiple objects are output
                    assert int(cell['outputs'][0]['data']['text/plain']) == next(answers)

def test_mapping_results():
    """Makes sure that you get the correct mapping results similar to test_compare_results but with
    more non-deterministic outputs"""
    for fname in maps.keys():
        with open(os.path.join('./',fname+'_ipy.ipynb'),'r') as f:
            nb = nbformat.read(f,nbformat.NO_CONVERT)
            answers = maps[fname]
            ans = []
            for num,cell in enumerate(nb['cells']):
                if 'outputs' in cell and len(cell['outputs']):
                    ans.append(cell['outputs'][0]['data']['text/plain'])
            assert len([val for val in ans if val in answers]) == len(answers)