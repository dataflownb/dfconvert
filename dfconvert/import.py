import ast
import astor
import IPython.core
from dfconvert.constants import DEFAULT_ID_LENGTH,DF_CELL_PREFIX,IPY_CELL_PREFIX
import re
import os, binascii
import json

def transform(line):
    #Changes Out[aaa] and Out["aaa"] to Out_aaa
    return re.sub('Out_([0-9A-Fa-f]{'+str(DEFAULT_ID_LENGTH)+'})', r'Out[\1]',line)

def remove_comment(line):
    #Removes comments from export.py
    return line.replace(DF_CELL_PREFIX,'')

def transform_last_node(nnode):
    for node in nnode.targets:
        for name in ast.walk(node):
            if isinstance(name,ast.Name):
                reobj = re.search('(Out_)?([0-9A-Fa-f]{6})',name.id)
                if(reobj):
                    #Only need to reassign Assign to expression if it contains an O
                    return ast.Expr(nnode.value)
    return nnode


out_transformer = IPython.core.inputtransformer.StatelessInputTransformer(transform)
comment_remover = IPython.core.inputtransformer.StatelessInputTransformer(remove_comment)

transformer = IPython.core.inputsplitter.IPythonInputSplitter(physical_line_transforms=[out_transformer,comment_remover])
remove_magics = IPython.core.inputsplitter.IPythonInputSplitter()

def import_dfpynb(filename,d):
    fullpath = os.getcwd()
    for cell in d['cells']:
        if (cell['cell_type'] != "code"):
            continue
        if 'metadata' in cell and 'dfkernel_old_id' in cell['metadata']:
            exec_count = cell['metadata']['dfkernel_old_id']
            del cell['metadata']['dfkernel_old_id']
        else:
            exec_count = int(binascii.b2a_hex(os.urandom(6)), 16)
        csource = cell['source']
        if not isinstance(csource, str):
            csource = "".join(csource)
        csource = remove_magics.transform_cell(csource)
        cast = ast.parse(csource)
        if cast.body and isinstance(cast.body[-1], ast.Assign):
            cast.body[-1] = transform_last_node(cast.body[-1])
            csource = astor.to_source(cast)
        csource = IPY_CELL_PREFIX + transformer.transform_cell(csource).rstrip()
        cell['execution_count'] = exec_count
        cell['source'] = csource

    # change the kernelspec
    # FIXME what if this metadata doesn't exist?
    d["metadata"]["kernelspec"]["display_name"] = "DFPython 3"
    d["metadata"]["kernelspec"]["name"] = "dfpython3"

    if (re.search('_ipy', filename) != None):
        ipy = str.index(filename, '_ipy')
        filename = filename[:ipy] + filename[ipy + len('_ipy'):]
    filename = os.path.join(fullpath, filename[:-6] + "_dfpy" + filename[-6:])
    with open(filename, 'w') as outfile:
        json.dump(d, outfile, indent=4)
    return filename

def bundle(handler, model):
    """Converts the existing IPython Notebook file into a Dataflow Kernel File"""
    notebook_filename = model['name']
    notebook_content = model['content']
    handler.finish('File Exported As: {}'.format(import_dfpynb(notebook_filename,notebook_content)))