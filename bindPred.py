import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

import warnings
warnings.filterwarnings("ignore")

import os
import sys
import yaml
import timeit

import matplotlib.pyplot as plt

from dataParser.pdbParse import read_PDB, binding_pocket_selection, ligand_parse_write, ligand_atom_type_calc

from graph.distComp import elementsDistanceCalc, atomTypesDistanceCalc
from graph.weigthsCalc import atomSubgraphsWeights, elementSubgraphsWeights
from graph.build_graph import graph_builder, MyDataset
from graph.graph_descriptors import compute_adjacency_matrix, compute_laplacian_matrix

from models.GNN import gnn

from utils.utils import visual_graph, save_graph, read_graph, data_loaders, loss_plot, r_squared

from spektral.transforms.normalize_adj import NormalizeAdj

from keras.optimizers import Adam, Nadam
from keras.callbacks import ModelCheckpoint


def parseyaml():

    with open(sys.argv[1]) as ctrl_file:
        params = yaml.load(ctrl_file, Loader=yaml.FullLoader)

    return params

def main():
    start = timeit.default_timer()

    param_args = parseyaml()

    if 'fitting' not in param_args or param_args['fitting'] == False:

        for file in os.listdir(param_args['path']):
            if file.endswith('.pdb') and not file.startswith('lig'):
                system, prody_system = read_PDB(param_args['path'] + file, param_args['ligand_name'])
                selected_protein, selected_ligand = binding_pocket_selection(system, prody_system, param_args['ligand_name'], param_args['selection_radius'], param_args['center'])

                if param_args['nodes'] == 'atoms':

                    ligand_path = ligand_parse_write(
                        path=param_args['path'] + file, out=param_args['output'], lig_name=param_args['ligand_name'])
                    selected_ligand_at = ligand_atom_type_calc(
                        ligand=selected_ligand, ligand_path=ligand_path)
                    interactions, atom_types, ligand_atom_types, protein_atom_types = atomTypesDistanceCalc(
                        binding_pocket=selected_protein, ligand=selected_ligand_at)
                    final_weigths, atom_combinations = atomSubgraphsWeights(atom_interactions=interactions, types=atom_types, decay_function=param_args['decay_function'],
                                                                            ligand_atom_types=ligand_atom_types, protein_atom_types=protein_atom_types)

                elif param_args['nodes'] == 'elements':
                    interactions, elements, ligand_elements, protein_elements = elementsDistanceCalc(
                        binding_pocket=selected_protein, ligand=selected_ligand)
                    final_weigths, atom_combinations = elementSubgraphsWeights(atom_interactions=interactions, types=elements, decay_function=param_args['decay_function'],
                                                                               ligand_atom_types=ligand_elements, protein_atom_types=protein_elements)

                graph_strength, graph_distance = graph_builder(weights=final_weigths)

                visual_graph(graph_strength, out=param_args['output'] + file.split('.')[0] + '_graph_strength')
                visual_graph(graph_distance, out=param_args['output'] + file.split('.')[0] + '_graph_distance')

                save_graph(graph=graph_strength, out=param_args['output'] + file)

                adj_matrix = compute_adjacency_matrix(graph_strength, out=param_args['output'] + file)

            #    lap_matrix = compute_laplacian_matrix(graph_strength)

    elif param_args['fitting'] == 'GNN':

        dataset = MyDataset(path=param_args['path'], out=param_args['output'], target=param_args['target'], transforms=NormalizeAdj())

        print(f'Number of loaded graphs: {dataset.n_graphs}')

        tr_loader, te_loader = data_loaders(data=dataset, batch_size=param_args['batch_size'],
                                epochs=param_args['epochs'])

        GNN = gnn.GraphNeuralNetwork(2000)

        opt = Nadam(learning_rate=param_args['learning_rate'])

        GNN.compile(optimizer = opt, loss= 'huber', metrics = ['mean_absolute_error', r_squared])

        history = GNN.fit(tr_loader.load(), steps_per_epoch=tr_loader.steps_per_epoch, epochs=param_args['epochs'])
        loss_plot(history, param_args['output'] + '_' + param_args['fitting'])

        GNN.summary()

        GNN.evaluate(te_loader.load(), steps=te_loader.steps_per_epoch)

    print(f"\nExecuted in {datetime.now()-start}")

    return 0


if __name__ == '__main__':
    main()
