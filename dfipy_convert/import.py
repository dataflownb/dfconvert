import json
import redbaron
import re
import os, binascii

def import_dfpynb(filename,d):
    fullpath = os.getcwd()
    for cell in d['cells']:
        if (cell['cell_type'] != "code"):
            continue
        nlist = ""
        mlist = []
        exec_count = int(binascii.b2a_hex(os.urandom(6)), 16)
        csource = cell['source']
        if (type(cell['source']) == str):
            csource = cell['source'].rstrip('\n ').split('\n')
        for line in csource:
            if len(line) > 0 and (line[0] == '%' or line[0] == '!'):
                mlist.append(line + '\n')
                continue
            elif (re.search('###Out_[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]###',
                            line) != None):
                exec_count = int(
                    re.search('(?<=###Out_)[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f](?<!###)',
                              line).group(0), 16)
                continue
            nlist = nlist + line.rstrip() + '\n'
        nlist = redbaron.RedBaron(nlist)
        for node in nlist.find_all("name", value=lambda value: re.search('(?<=Out_)' + hex(exec_count)[2:], value)):
            try:
                val = nlist.index(node.parent)
            except ValueError:
                pass
            del nlist[val]
        for node in nlist.find_all("name", value=lambda value: re.search(
                '(?<=Out_)[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]', value)):
            node.value = "Out['" + str(node.value)[len("Out_"):] + "']"
        cell['execution_count'] = exec_count
        if (len(cell['outputs']) > 0):
            cell['outputs'][0]['execution_count'] = exec_count
        for x in range(len(nlist)):
            mlist.append((nlist[x].dumps()) + '\n')
        cell['source'] = mlist

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