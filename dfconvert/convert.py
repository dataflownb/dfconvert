import asttokens
from collections import OrderedDict
import re
import ast
import astor
from . import make_ipy
from .topological import topological
from IPython.core.inputtransformer2 import TransformerManager
from .display_cell import display_variable_cell
from .constants import DEFAULT_ID_LENGTH, DF_CELL_PREFIX

def convert_notebook(notebook, md_above = False, full_transform=False, out_mode=False):
    cell_template = {
         "cell_type": "code",
         "execution_count": None,
         "metadata": {},
         "outputs": [],
         "source": []
        }
    
    try:
        code_cells_ref = dict()
        non_code_cells_ref = OrderedDict()
        downlinks = dict()
        nb_output_tags = dict()
        non_code_cells_block = dict()
        non_code_cells_seq = dict()
        transformer_manager = TransformerManager()
        latest_non_code_cell = None
        
        for cell in notebook['cells']:
            output_tags = list()
            id = cell['id'].split('-')[0]
            if cell['cell_type'] != "code":
                non_code_cells_seq[id] = []
                if latest_non_code_cell is not None and len(non_code_cells_block[latest_non_code_cell]) == 0:
                    del non_code_cells_block[latest_non_code_cell]
                    non_code_cells_seq[id] += non_code_cells_seq[latest_non_code_cell] + [non_code_cells_ref[latest_non_code_cell]]
                    del non_code_cells_seq[latest_non_code_cell]

                latest_non_code_cell = id
                non_code_cells_ref[id] = cell
                non_code_cells_block[id] = set()

            else:
                if latest_non_code_cell is not None and len(cell['source']) > 0:
                    non_code_cells_block[latest_non_code_cell].add(id)
                for output in range(len(cell['outputs'])):
                    if cell['outputs'][output].get('metadata') and cell['outputs'][output]['metadata'].get('output_tag'):
                        output_tags.append(cell['outputs'][output]['metadata']['output_tag'])
                        
                    if cell['outputs'][output].get('execution_count'):
                        cell['outputs'][output]['execution_count'] = None

                    if 'execution_count' in cell['outputs'][output].keys() and cell['outputs'][output].get('output_type') and cell['outputs'][output]['output_type'] in ['stream', 'display_data', 'error', 'update_display_data', 'clear_output']:
                        del cell['outputs'][output]['execution_count']
                
                nb_output_tags[id] = output_tags
                code_cells_ref[id] = [cell]

        for uuid, cell in code_cells_ref.items():
            make_ipy.ref_uuids = set()
            code= transformer_manager.transform_cell(cell[0]['source'])
            code = make_ipy.convert_dollar(code, make_ipy.identifier_replacer, {})
            code = make_ipy.convert_identifier(code, make_ipy.dollar_replacer)
            code = make_ipy.convert_output_tags(code, nb_output_tags[uuid], uuid, code_cells_ref.keys())
            cast = asttokens.ASTTokens(code, parse=True)
            code = make_ipy.transform_out_refs(code, cast)
            
            if full_transform:
                def transform_outrefs(source_code):
                    # Changes Out[aaa] and Out["aaa"] to Out_aaa
                    return re.sub(r'Out\[["|\']?([0-9A-Fa-f]{' + str(DEFAULT_ID_LENGTH) + r'})["|\']?\]', r'Out_\1', source_code)
                code = transform_outrefs(code)

            cast = asttokens.ASTTokens(code, parse=True)
            code = make_ipy.transform_last_node(code, cast, uuid)

            #Create list of all out_tags
            valid_tags = []
            if ('outputs' in cell[0]):
                for output in cell[0]['outputs']:
                    if ('metadata' in output and 'output_tag' in output['metadata']):
                        valid_tags.append(output['metadata']['output_tag'])

            cast = asttokens.ASTTokens(code, parse=True)
            code, out_targets = make_ipy.out_assign(code, cast, uuid, valid_tags)

            code_cells_ref[uuid][0]['source'] = code.strip()

            if out_mode:
                    tree = ast.parse(cell[0]['source'])
                    if out_targets:
                        if isinstance(out_targets, ast.Tuple):
                            for j in out_targets.elts:
                                new_cell = dict(cell_template)
                                new_cell['source'] = DF_CELL_PREFIX + str(astor.to_source(j)).rstrip()
                                code_cells_ref[uuid].append(new_cell)
                    if tree.body and isinstance(tree.body[-1], ast.Assign) and isinstance(tree.body[-1].targets, list):
                        for count, i in enumerate(tree.body[-1].targets):
                            if len(tree.body[-1].targets) == count+1 and isinstance(i,ast.Name) and len(code_cells_ref[uuid]) == 1:
                                new_cell = dict(cell_template)
                                new_cell['source'] = DF_CELL_PREFIX + str(i.id)
                                code_cells_ref[uuid].append(new_cell)
                            if isinstance(i, ast.Tuple):
                                for j in i.elts:
                                    if isinstance(j, ast.Name):
                                        new_cell = dict(cell_template)
                                        new_cell['source'] = DF_CELL_PREFIX + str(j.id)
                                        code_cells_ref[uuid].append(new_cell)
            else:
                '''
                case when the exported tag in metadata is of type: "[UUID][0]"
                '''
                def replace_id(input_string):
                    pattern = r'\[([a-zA-Z0-9]+)\]\[(\d+)\]'
                    replacement = r'Out_\1[\2]'
                    output_string = re.sub(pattern, replacement, input_string)
                    return output_string


                exported_variables= ""
                if nb_output_tags.get(uuid):
                    exported_variables = '{ '
                    for value in nb_output_tags[uuid]:
                        if len(value) >= 8 and (value[:8] in code_cells_ref.keys() or uuid == value[:8]):
                            continue
                        if uuid in value:
                            tag = replace_id(value)
                            exported_variables += f'"{tag}": {tag},'
                        else:
                            exported_variables += f'"{value}_{uuid}": {value}_{uuid},'
                    exported_variables += '}'

                if len(exported_variables) > 3:
                    code += '\ndisplay_variables(' + exported_variables + ')'
                elif ('Out_'+uuid) in code:
                        exported_variables = f'"Out_{uuid}": Out_{uuid},'
                        code += '\ndisplay_variables( { ' + exported_variables + ' })'

                code_cells_ref[uuid][0]['source'] = code

            downlinks[uuid] = [id for id in make_ipy.ref_uuids]

        sorted_order = list(topological(downlinks))
        ordered_cells = list()

        if md_above:
            ordered_cells = [non_code_cells for non_code_cells in non_code_cells_ref.values()]

        for cell_id in sorted_order[::-1]:
            if not md_above:
                for id, code_ids in non_code_cells_block.items():
                    if cell_id in code_ids:
                        if non_code_cells_seq.get(id):
                            ordered_cells += non_code_cells_seq[id]
                        ordered_cells.append(non_code_cells_ref[id])
                        del non_code_cells_block[id]
                        break
            #ordered_cells.append(code_cells_ref[cell_id])
            ordered_cells = ordered_cells + code_cells_ref[cell_id]
            
        if not md_above:
            for cell_id in non_code_cells_block.keys():
                ordered_cells.append(non_code_cells_ref[cell_id])

        notebook['cells'] = ordered_cells if out_mode else display_variable_cell + ordered_cells

        if notebook.get('metadata') and notebook['metadata'].get('kernelspec'):
            if notebook["metadata"]["kernelspec"].get('display_name'):
                notebook["metadata"]["kernelspec"]["display_name"] = "Python 3"
            if notebook["metadata"]["kernelspec"].get('name'):
                notebook["metadata"]["kernelspec"]["name"] = "python3"

        return notebook
    except Exception as e:
        return ''