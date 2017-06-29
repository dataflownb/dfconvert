import json
import redbaron
import os
from dfipy_convert.topological import topological

def export_dfpynb(filename,d):
    fullpath = os.getcwd()
    edgelist = {}
    cellindices = {}
    cellflag = 0
    prevind = ""

    for count, cell in enumerate(d['cells']):
        if (cell['cell_type'] != "code"):
            if (cellflag == 1):
                cellindices[("umarkdown", prevind)] = count - 1
                prevind = "umarkdown" + prevind
            cellflag = 1
            continue
        nlist = ""
        mlist = []
        exec_count = hex(cell['execution_count'])[2:]
        for line in cell['source'].split('\n'):
            if (line[0] == '%'):
                mlist.append(line + '\n')
                continue
            nlist = nlist + line.rstrip() + '\n'
        nlist = redbaron.RedBaron(nlist)
        if (cellflag == 1):
            cellindices[("markdown", exec_count)] = count - 1
            cellflag = 0
        cellindices[exec_count] = count
        edgelist[exec_count] = []
        for node in nlist.find_all("name", value="Out"):
            edgelist[exec_count].append(node.parent.value[1].value.value.strip("'").strip('"'))
            newnodeval = "Out_" + node.parent.value[1].value.value.strip("'").strip('"')
            node.value = newnodeval
            del node.parent.value[1]
        if (len(cell['outputs']) > 0 and len(nlist) > 0):
            listlen = len(nlist) + len(mlist) - 1
            nlist[listlen].insert_after("Out_" + exec_count + " = " + nlist[listlen].dumps())
            nlist[listlen + 1].insert_after("Out_" + exec_count)
            # print("Out_" + exec_count + " = " + nlist[len(nlist)-2].dumps())
        for x in range(len(nlist)):
            mlist.append((nlist[x].dumps()) + '\n')
        mlist.append("###Out_" + exec_count + "###\n")
        prevind = exec_count
        cell['source'] = mlist

    topologic = list(reversed(topological(edgelist)))

    for index in cellindices:
        if (index[0] == 'markdown'):
            topologic.insert(topologic.index(index[1]), index)
        elif (index[0] == 'umarkdown'):
            umcount = str.count(index[1], 'umarkdown')
            # Special case single markdown cell at top of page
            if (index == 'umarkdown'):
                topologic.insert(0, index)
                continue
            topologic.insert((topologic.index(index[1][umcount * len(index[0]):])), index)

    origlist = d['cells'].copy()
    for count, cellno in enumerate(topologic):
        cell = origlist[cellindices[cellno]]
        if (cell['cell_type'] == "code"):
            cell['execution_count'] = count + 1
            if (len(cell['outputs']) > 0):
                cell['outputs'][0]['execution_count'] = count + 1
        d['cells'][count] = cell

    filename = os.path.join(fullpath, filename[:-6] + "_ipy" + filename[-6:])
    with open(filename, 'w') as outfile:
        json.dump(d, outfile, indent=4)
    return filename

def bundle(handler, model):
    """Converts the existing IPython Notebook file into a Dataflow Kernel File"""
    notebook_filename = model['name']
    notebook_content = model['content']
    handler.finish('File Exported As: {}'.format(export_dfpynb(notebook_filename,notebook_content)))